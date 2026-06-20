from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

User = get_user_model()


@override_settings(
    STORE_REVIEW_USER_PHONE='998911234567',
    STORE_REVIEW_USER_OTP='5353',
)
class StoreReviewLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_send_otp_skips_sms_for_review_phone(self):
        resp = self.client.post(
            '/api/v1/auth/login/',
            {'phone': '+998911234567'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['message'], 'СМС код отправлен')

    def test_verify_review_otp_without_prior_send(self):
        resp = self.client.post(
            '/api/v1/auth/verify-otp/',
            {'phone': '998911234567', 'code': '5353'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)
        user = User.objects.get(phone='998911234567')
        self.assertTrue(user.is_verified)
        self.assertTrue(user.groups.filter(name='User').exists())

    def test_wrong_review_code_rejected(self):
        resp = self.client.post(
            '/api/v1/auth/verify-otp/',
            {'phone': '998911234567', 'code': '0000'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_full_flow_send_then_verify(self):
        self.client.post('/api/v1/auth/login/', {'phone': '998911234567'}, format='json')
        resp = self.client.post(
            '/api/v1/auth/verify-otp/',
            {'phone': '998911234567', 'code': '5353'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
