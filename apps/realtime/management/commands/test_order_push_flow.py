"""
Buyurtma yaratish → tugash: har bosqichda kim push oladi, token/FCM holati.

  python manage.py test_order_push_flow
  python manage.py test_order_push_flow --order-id 42
  python manage.py test_order_push_flow --order-id 42 --run
  python manage.py test_order_push_flow --customer-id 5 --operator-id 8 --courier-id 12 --run
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, List, Optional

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import UserDevice
from apps.core.enums import OrderStatus, PaymentType, UserGroup
from apps.orders.models import Order, OrderCourier
from apps.realtime.models import Notification
from apps.realtime.services.fcm import (
    firebase_credentials_status,
    probe_fcm_http_api,
    reset_fcm_auth_state,
    send_fcm_to_tokens,
    verify_firebase_oauth,
)
from apps.realtime.services.order_notifications import (
    _new_order_push_recipient_ids,
    notify_courier_assigned,
    notify_customer_cash_confirmed,
    notify_customer_delivered,
    notify_customer_status_change,
    notify_operators_new_order,
    on_order_created,
)

User = get_user_model()


@dataclass
class FlowStep:
    key: str
    label: str
    recipient_hint: str
    run: Callable[[], None]


def _token_count(user_id: int) -> int:
    return UserDevice.objects.filter(
        user_id=user_id,
        is_active=True,
    ).exclude(device_token='').count()


def _user_line(user_id: int) -> str:
    try:
        u = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return f'id={user_id} (topilmadi)'
    groups = list(u.groups.values_list('name', flat=True))
    tokens = _token_count(user_id)
    flag = 'OK' if tokens else 'TOKEN YO‘Q'
    return f'id={user_id} phone={u.phone} groups={groups} fcm={tokens} [{flag}]'


class Command(BaseCommand):
    help = 'Buyurtma push oqimi: diagnostika yoki --run bilan haqiqiy FCM.'

    def add_arguments(self, parser):
        parser.add_argument('--order-id', type=int, help='Mavjud buyurtma ID')
        parser.add_argument('--customer-id', type=int, help='Mijoz user id (--run da test order uchun)')
        parser.add_argument('--operator-id', type=int, help='Operator (yangi buyurtma push)')
        parser.add_argument('--courier-id', type=int, help='Kuryer (add-courier push)')
        parser.add_argument(
            '--run',
            action='store_true',
            help='Har bosqichda notify chaqirish + FCM yuborish (DB ga Notification yoziladi)',
        )
        parser.add_argument(
            '--cash',
            action='store_true',
            help='Test order: naqd to‘lov (default cash)',
        )

    def handle(self, *args, **options):
        reset_fcm_auth_state()
        self._print_fcm_header()

        order = self._resolve_order(options)
        if not order:
            self._print_operators_summary()
            self._print_why_push_fails()
            return

        customer_id = order.user_id
        courier_id = options.get('courier_id')
        if not courier_id:
            oc = OrderCourier.objects.filter(order_id=order.pk).first()
            courier_id = oc.courier_id if oc else None

        steps = self._build_steps(order.pk, customer_id, courier_id)
        self.stdout.write('')
        self.stdout.write(f'=== Buyurtma #{order.pk} ({order.payment_type}, status={order.status}) ===')
        self.stdout.write(f'  Mijoz: {_user_line(customer_id)}')
        self.stdout.write('  Operator/Admin push qabul qiluvchilar:')
        for uid in _new_order_push_recipient_ids():
            self.stdout.write(f'    {_user_line(uid)}')
        if courier_id:
            self.stdout.write(f'  Kuryer: {_user_line(courier_id)}')
        else:
            self.stdout.write(self.style.WARNING('  Kuryer biriktirilmagan — add-courier push sinovdan o‘tkazilmaydi'))

        self.stdout.write('')
        self.stdout.write('=== Bosqichlar (yaratish → tugash) ===')
        for step in steps:
            self.stdout.write(f'  • {step.key}: {step.label}')
            self.stdout.write(f'      → {step.recipient_hint}')

        if not options.get('run'):
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'Faqat diagnostika (--run yo‘q). Haqiqiy push sinovi:\n'
                f'  python manage.py test_order_push_flow --order-id {order.pk} --run\n'
                f'  python manage.py send_test_push --user-id <operator_id>\n'
                f'  python manage.py check_fcm_config --user-id <operator_id>',
            ))
            self._print_why_push_fails()
            return

        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('=== --run: har bosqichda FCM ==='))
        total_sent = 0
        for step in steps:
            before = Notification.objects.count()
            sent = self._run_step(step)
            after = Notification.objects.count()
            total_sent += sent
            self.stdout.write(
                f'  {step.key}: notifications +{after - before}, fcm_sent={sent}',
            )
        self.stdout.write('')
        if total_sent == 0:
            self.stdout.write(self.style.ERROR('FCM: 0 ta yuborildi — quyidagi sabablarni tekshiring'))
            self._print_why_push_fails()
        else:
            self.stdout.write(self.style.SUCCESS(f'Jami FCM muvaffaqiyatli: {total_sent}'))

    def _print_fcm_header(self) -> None:
        fb = firebase_credentials_status()
        self.stdout.write('=== Firebase / FCM ===')
        self.stdout.write(f"  project_id: {fb.get('project_id')}")
        self.stdout.write(f"  private_key_ok: {fb.get('private_key_ok')}")
        if fb.get('issues'):
            for issue in fb['issues']:
                self.stdout.write(self.style.ERROR(f'  ! {issue}'))
            return
        oauth = verify_firebase_oauth()
        if not oauth.get('ok'):
            self.stdout.write(self.style.ERROR(f"  OAuth: {oauth.get('detail')}"))
            return
        api = probe_fcm_http_api()
        if api.get('ok'):
            self.stdout.write(self.style.SUCCESS(f"  API: {api.get('detail')}"))
        else:
            self.stdout.write(self.style.ERROR(f"  API: {api.get('detail')}"))

    def _resolve_order(self, options) -> Optional[Order]:
        order_id = options.get('order_id')
        if order_id:
            try:
                return Order.objects.get(pk=order_id, is_deleted=False)
            except Order.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Order id={order_id} topilmadi'))
                return None

        if not options.get('run'):
            self.stdout.write(self.style.WARNING('--order-id bering yoki --run bilan test order yarating'))
            return None

        customer_id = options.get('customer_id')
        if not customer_id:
            self.stdout.write(self.style.ERROR('--run uchun --order-id yoki --customer-id kerak'))
            return None

        payment = PaymentType.CASH.value if options.get('cash', True) else PaymentType.CARD.value
        with transaction.atomic():
            order = Order.objects.create(
                user_id=customer_id,
                status=OrderStatus.CREATED.value,
                payment_type=payment,
                estimated_total=Decimal('1000'),
            )
        self.stdout.write(self.style.SUCCESS(f'Test order yaratildi: id={order.pk}'))
        return order

    def _build_steps(
        self,
        order_id: int,
        customer_id: int,
        courier_id: Optional[int],
    ) -> List[FlowStep]:
        steps: List[FlowStep] = [
            FlowStep(
                '1_created',
                'POST /orders/ — yangi buyurtma',
                'Operator + Admin + Super Admin',
                lambda: on_order_created(order_id),
            ),
            FlowStep(
                '2_confirmed',
                'Status → confirmed',
                'Mijoz (buyurtma egasi)',
                lambda: notify_customer_status_change(order_id, OrderStatus.CONFIRMED.value),
            ),
            FlowStep(
                '3_picking',
                'Status → picking',
                'Mijoz',
                lambda: notify_customer_status_change(order_id, OrderStatus.PICKING.value),
            ),
        ]
        if courier_id:
            steps.append(
                FlowStep(
                    '4_courier',
                    'POST add-courier → shipped',
                    f'Kuryer id={courier_id} + mijoz',
                    lambda: notify_courier_assigned(order_id, courier_id),
                ),
            )
            steps.append(
                FlowStep(
                    '5_shipped',
                    'Status → shipped (mijoz matni)',
                    'Mijoz',
                    lambda: notify_customer_status_change(order_id, OrderStatus.SHIPPED.value),
                ),
            )
        steps.extend([
            FlowStep(
                '6_delivered',
                'Status → delivered',
                'Mijoz (order_delivered)',
                lambda: notify_customer_delivered(order_id),
            ),
            FlowStep(
                '7_completed',
                'Cash QR confirm → completed',
                'Mijoz (order_status completed)',
                lambda: notify_customer_status_change(order_id, OrderStatus.COMPLETED.value),
            ),
            FlowStep(
                '8_cash_confirm',
                'Kuryer naqd tasdiqladi',
                'Mijoz (order_cash_confirmed)',
                lambda: notify_customer_cash_confirmed(order_id),
            ),
        ])
        return steps

    def _run_step(self, step: FlowStep) -> int:
        """on_commit callbacklarni ishga tushirish + FCM yuborilganlar soni."""
        from django.test import TestCase

        sent_holder: List[int] = [0]
        original = send_fcm_to_tokens

        def counting_send(tokens, *, title, body, data=None):
            n = original(tokens, title=title, body=body, data=data)
            sent_holder[0] += n
            return n

        import apps.realtime.services.notify as notify_mod

        notify_mod.send_fcm_to_tokens = counting_send
        try:
            with TestCase.captureOnCommitCallbacks(execute=True):
                step.run()
        finally:
            notify_mod.send_fcm_to_tokens = original
        return sent_holder[0]

    def _print_operators_summary(self) -> None:
        self.stdout.write('')
        self.stdout.write('=== Yangi buyurtma push qabul qiluvchilar ===')
        ids = _new_order_push_recipient_ids()
        if not ids:
            self.stdout.write(self.style.ERROR('  Hech kim yo‘q (Operator/Admin/Super Admin)'))
        for uid in ids:
            self.stdout.write(f'  {_user_line(uid)}')

    def _print_why_push_fails(self) -> None:
        self.stdout.write('')
        self.stdout.write('=== Push kelmasa — tez-tez sabablar ===')
        self.stdout.write('  1. .env: FIREBASE_PROJECT_ID / PRIVATE_KEY / CLIENT_EMAIL noto‘g‘ri yoki qisqa')
        self.stdout.write('  2. Google Cloud: Firebase Cloud Messaging API o‘chiq (403)')
        self.stdout.write('  3. Mobil google-services.json boshqa loyiha (token 400/404 → deactivate)')
        self.stdout.write('  4. POST /api/v1/devices/ qilinmagan — UserDevice token yo‘q')
        self.stdout.write('  5. Operator ilovasi: user Operator/Admin/Super Admin guruhida emas')
        self.stdout.write('  6. Kuryer push faqat add-courier dan keyin (status picking→shipped)')
        self.stdout.write('  7. HTTP_PROXY: NO_PROXY=fcm.googleapis.com kerak bo‘lishi mumkin')
