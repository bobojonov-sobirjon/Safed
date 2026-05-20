from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.core.enums import OrderStatus, PaymentType, UserGroup
from apps.orders.models import Order
from apps.realtime.models import Notification


class NotificationListApiTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name=UserGroup.OPERATOR.value)
        Group.objects.get_or_create(name=UserGroup.COURIER.value)
        self.operator = CustomUser.objects.create_user(phone='998901111111', password='x')
        self.operator.groups.add(Group.objects.get(name=UserGroup.OPERATOR.value))
        self.customer = CustomUser.objects.create_user(phone='998902222222', password='x')
        self.courier = CustomUser.objects.create_user(phone='998903333333', password='x')
        self.courier.groups.add(Group.objects.get(name=UserGroup.COURIER.value))
        self.order = Order.objects.create(
            user=self.customer,
            status=OrderStatus.CREATED.value,
            payment_type=PaymentType.CASH.value,
            estimated_total=Decimal('10000'),
        )
        Notification.objects.create(
            user=self.customer,
            type='order_status',
            title='T',
            body='B',
            data={'order_id': self.order.pk},
        )
        Notification.objects.create(
            user=self.operator,
            type='staff_new_order',
            title='S',
            body='SB',
            data={'order_id': self.order.pk},
        )
        Notification.objects.create(
            user=self.courier,
            type='courier_assigned',
            title='C',
            body='CB',
            data={'order_id': self.order.pk},
        )

    def test_customer_list_only_order_types(self):
        client = APIClient()
        client.force_authenticate(user=self.customer)
        r = client.get('/api/v1/notifications/customer/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['audience'], 'customer')
        types = {n['type'] for n in r.data['results']}
        self.assertEqual(types, {'order_status'})

    def test_staff_list_requires_role(self):
        client = APIClient()
        client.force_authenticate(user=self.customer)
        self.assertEqual(client.get('/api/v1/notifications/staff/').status_code, 403)

        client.force_authenticate(user=self.operator)
        r = client.get('/api/v1/notifications/staff/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual({n['type'] for n in r.data['results']}, {'staff_new_order'})

    def test_courier_list_requires_role(self):
        client = APIClient()
        client.force_authenticate(user=self.operator)
        self.assertEqual(client.get('/api/v1/notifications/courier/').status_code, 403)

        client.force_authenticate(user=self.courier)
        r = client.get('/api/v1/notifications/courier/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual({n['type'] for n in r.data['results']}, {'courier_assigned'})

    def test_unread_endpoint(self):
        Notification.objects.filter(user=self.customer).update(is_read=True)
        Notification.objects.create(
            user=self.customer,
            type='order_delivered',
            title='D',
            body='DB',
            is_read=False,
        )
        client = APIClient()
        client.force_authenticate(user=self.customer)
        r = client.get('/api/v1/notifications/unread/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['unread_count'], 1)
        self.assertEqual(len(r.data['results']), 1)
        self.assertEqual(r.data['results'][0]['type'], 'order_delivered')
