"""
Eskiz.uz SMS xizmati.
SMS yuborish - agar ishlamasa DEBUG=True bo'lsa code response da qaytadi.
"""
import requests
import os


def send_sms(phone: str, message: str, code: str = None) -> dict:
    """
    Eskiz.uz orqali SMS yuborish.
    :return: {'success': bool, 'message': str, 'code': str} - DEBUG=True bo'lsa code ham bor
    """
    email = os.getenv('ESKIZ_EMAIL')
    password = os.getenv('ESKIZ_PASSWORD')
    from_phone = os.getenv('ESKIZ_FROM', '4546')

    # Telefon formati: 998901234567
    if phone.startswith('+'):
        phone = phone[1:].replace(' ', '')
    elif phone.startswith('998'):
        pass
    elif phone.startswith('0'):
        phone = '998' + phone[1:]
    else:
        phone = '998' + phone

    if not email or not password:
        return {
            'success': False,
            'message': 'Настройки Eskiz.uz не найдены. Добавьте ESKIZ_EMAIL, ESKIZ_PASSWORD в .env',
            'code': code,
        }

    try:
        # 1. Token olish
        login_resp = requests.post(
            'https://notify.eskiz.uz/api/auth/login',
            data={'email': email, 'password': password},
            timeout=10,
        )
        if login_resp.status_code != 200:
            return {'success': False, 'message': 'Ошибка входа Eskiz', 'code': code}

        token = login_resp.json().get('data', {}).get('token')
        if not token:
            return {'success': False, 'message': 'Токен Eskiz не получен', 'code': code}

        # 2. SMS yuborish
        headers = {'Authorization': f'Bearer {token}'}
        sms_resp = requests.post(
            'https://notify.eskiz.uz/api/message/sms/send',
            headers=headers,
            data={
                'mobile_phone': phone,
                'message': message,
                'from': from_phone,
            },
            timeout=10,
        )

        if sms_resp.status_code == 200 and sms_resp.json().get('status') == 'success':
            return {'success': True, 'message': 'СМС отправлено', 'code': code}

        # SMS yuborilmadi - DEBUG da code qaytaramiz
        from django.conf import settings
        if settings.DEBUG and code:
            return {'success': False, 'message': 'СМС не отправлено (DEBUG: код возвращён в ответе)', 'code': code}

        return {'success': False, 'message': sms_resp.json().get('message', 'Ошибка СМС'), 'code': code}

    except Exception as e:
        from django.conf import settings
        return {
            'success': False,
            'message': str(e),
            'code': code if settings.DEBUG else None,
        }
