from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import UserDevice
from apps.realtime.services.fcm import send_fcm_to_tokens

User = get_user_model()


class FcmInvalidTokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='998908080808', password='pass')
        self.device = UserDevice.objects.create(
            user=self.user,
            device_token='string',
            device_type='android',
            is_active=True,
        )

    def test_placeholder_token_deactivated_without_firebase(self):
        sent = send_fcm_to_tokens(['string'], title='T', body='B')
        self.assertEqual(sent, 0)
        self.device.refresh_from_db()
        self.assertFalse(self.device.is_active)
