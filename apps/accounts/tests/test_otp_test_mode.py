"""OTP test mode: fixed code for all phones."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

User = get_user_model()


@override_settings(OTP_TEST_CODE='1111', DEBUG=True)
class OtpTestModeTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_login_uses_fixed_otp(self):
        phone = '998901112233'
        send = self.client.post('/api/v1/auth/login/', {'phone': phone}, format='json')
        self.assertEqual(send.status_code, 200, send.data)
        self.assertEqual(send.data.get('code'), '1111')

        verify = self.client.post(
            '/api/v1/auth/verify-otp/',
            {'phone': phone, 'code': '1111'},
            format='json',
        )
        self.assertEqual(verify.status_code, 200, verify.data)
        self.assertIn('access', verify.data)
        self.assertTrue(User.objects.filter(phone=phone).exists())

    def test_wrong_code_rejected(self):
        phone = '998904445566'
        self.client.post('/api/v1/auth/login/', {'phone': phone}, format='json')
        verify = self.client.post(
            '/api/v1/auth/verify-otp/',
            {'phone': phone, 'code': '9999'},
            format='json',
        )
        self.assertEqual(verify.status_code, 400)
