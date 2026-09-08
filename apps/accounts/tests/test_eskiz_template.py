from django.test import SimpleTestCase, override_settings

from apps.accounts.services.eskiz import (
    format_otp_message,
    normalize_phone,
    _sms_accepted,
)


class EskizTemplateTests(SimpleTestCase):
    def test_normalize_phone(self):
        self.assertEqual(normalize_phone('+998901234567'), '998901234567')
        self.assertEqual(normalize_phone('901234567'), '998901234567')

    @override_settings(
        ESKIZ_OTP_TEMPLATE='Safet Go mobil ilovasiga kirish uchun tasdiqlash kodi: {code}. Kodni hech kimga bermang'
    )
    def test_approved_template(self):
        msg = format_otp_message('4821')
        self.assertEqual(
            msg,
            'Safet Go mobil ilovasiga kirish uchun tasdiqlash kodi: 4821. Kodni hech kimga bermang',
        )

    def test_waiting_status_is_success(self):
        self.assertTrue(_sms_accepted(200, {'status': 'waiting', 'id': 'abc'}))
        self.assertTrue(_sms_accepted(200, {'status': 'success'}))
        self.assertFalse(_sms_accepted(400, {'status': 'waiting'}))

    def test_otp_is_four_digits(self):
        from apps.accounts.services.otp import generate_otp, resolve_login_otp

        code = generate_otp()
        self.assertEqual(len(code), 4)
        self.assertTrue(code.isdigit())
        self.assertEqual(len(resolve_login_otp()), 4)
