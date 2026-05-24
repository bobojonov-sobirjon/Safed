from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.models import UserDevice
from apps.realtime.services.marketing_push import (
    DAILY_CART_REMINDER_BODY,
    DAILY_CART_REMINDER_TITLE,
    send_daily_cart_reminder_to_all,
)
from apps.realtime.tasks import send_daily_cart_reminder_push

User = get_user_model()


class DailyCartReminderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='998909090909', password='pass')
        UserDevice.objects.create(
            user=self.user,
            device_token='token-abc',
            device_type='android',
            is_active=True,
        )

    @patch('apps.realtime.services.marketing_push.send_fcm_to_tokens', return_value=1)
    def test_sends_uzbek_copy_to_all_tokens(self, mock_fcm):
        result = send_daily_cart_reminder_to_all()
        self.assertEqual(result['tokens'], 1)
        self.assertEqual(result['sent'], 1)
        mock_fcm.assert_called_once()
        _, kwargs = mock_fcm.call_args
        self.assertEqual(kwargs['title'], DAILY_CART_REMINDER_TITLE)
        self.assertIn('unutdingiz', kwargs['title'].lower())
        self.assertEqual(kwargs['body'], DAILY_CART_REMINDER_BODY)
        self.assertEqual(kwargs['data']['type'], 'daily_cart_reminder')

    @override_settings(DAILY_CART_REMINDER_ENABLED=False)
    @patch('apps.realtime.services.marketing_push.send_daily_cart_reminder_to_all')
    def test_task_skipped_when_disabled(self, mock_send):
        out = send_daily_cart_reminder_push()
        self.assertTrue(out.get('skipped'))
        mock_send.assert_not_called()

    @patch('apps.realtime.services.marketing_push.send_daily_cart_reminder_to_all', return_value={'sent': 1})
    def test_task_calls_service_when_enabled(self, mock_send):
        out = send_daily_cart_reminder_push()
        self.assertEqual(out['sent'], 1)
        mock_send.assert_called_once()
