from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.accounts.services.user_lifecycle import (
    UserDeleteError,
    delete_own_account,
    delete_or_deactivate_user,
)
from apps.core.enums import OrderStatus, PaymentType, UserGroup
from apps.orders.models import Order


class UserDeleteTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name=UserGroup.SUPER_ADMIN.value)
        Group.objects.get_or_create(name=UserGroup.USER.value)

        self.admin = CustomUser.objects.create_user(phone='998901010101', password='pass')
        self.admin.groups.add(Group.objects.get(name=UserGroup.SUPER_ADMIN.value))

        self.customer = CustomUser.objects.create_user(phone='998902020202', password='pass')
        self.customer.groups.add(Group.objects.get(name=UserGroup.USER.value))

        Order.objects.create(
            user=self.customer,
            status=OrderStatus.CREATED.value,
            payment_type=PaymentType.CASH.value,
            estimated_total=Decimal('1000'),
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_user_with_orders_is_deactivated_not_deleted(self):
        result = delete_or_deactivate_user(self.customer)
        self.assertTrue(result['deactivated'])
        self.assertFalse(result['deleted'])
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)
        self.assertTrue(self.customer.phone.startswith('deleted_'))

    def test_delete_api_returns_200_when_deactivated(self):
        orphan = CustomUser.objects.create_user(phone='998903030303', password='pass')
        Order.objects.create(
            user=orphan,
            status=OrderStatus.CREATED.value,
            payment_type=PaymentType.CASH.value,
            estimated_total=Decimal('500'),
        )
        response = self.client.delete(f'/api/v1/users/{orphan.pk}/delete/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('deactivated'))


class UserSelfDeleteTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name=UserGroup.USER.value)
        self.user = CustomUser.objects.create_user(phone='998904040404', password='pass')
        self.user.groups.add(Group.objects.get(name=UserGroup.USER.value))
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_blocked_when_active_order(self):
        Order.objects.create(
            user=self.user,
            status=OrderStatus.PICKING.value,
            payment_type=PaymentType.CASH.value,
            estimated_total=Decimal('1000'),
        )
        with self.assertRaises(UserDeleteError) as ctx:
            delete_own_account(self.user)
        self.assertEqual(ctx.exception.code, 'active_orders')
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_allowed_when_only_completed_order(self):
        Order.objects.create(
            user=self.user,
            status=OrderStatus.COMPLETED.value,
            payment_type=PaymentType.CASH.value,
            estimated_total=Decimal('1000'),
        )
        result = delete_own_account(self.user)
        self.assertTrue(result['deactivated'])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_hard_delete_when_no_orders(self):
        fresh = CustomUser.objects.create_user(phone='998905050505', password='pass')
        result = delete_own_account(fresh)
        self.assertTrue(result['deleted'])

    def test_api_returns_400_with_active_order(self):
        Order.objects.create(
            user=self.user,
            status=OrderStatus.SHIPPED.value,
            payment_type=PaymentType.CARD.value,
            estimated_total=Decimal('2000'),
        )
        resp = self.client.delete('/api/v1/users/me/delete/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['code'], 'active_orders')
        self.assertGreater(resp.data['active_orders_count'], 0)

    def test_api_deactivates_when_completed_only(self):
        Order.objects.create(
            user=self.user,
            status=OrderStatus.REJECTED.value,
            payment_type=PaymentType.CASH.value,
            estimated_total=Decimal('500'),
        )
        resp = self.client.delete('/api/v1/users/me/delete/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('deactivated'))
