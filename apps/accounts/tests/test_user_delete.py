from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.accounts.services.user_lifecycle import delete_or_deactivate_user
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
