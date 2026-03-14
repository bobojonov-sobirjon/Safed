"""Rus tilidagi xato xabarlari"""
from rest_framework.views import exception_handler
from rest_framework.response import Response


RU_TRANSLATIONS = {
    'This field is required.': 'Обязательное поле.',
    'This field may not be blank.': 'Поле не может быть пустым.',
    'Invalid data. Expected a dictionary, but got': 'Неверные данные. Ожидается объект, получено',
    'A user with that username already exists.': 'Пользователь с таким именем уже существует.',
    'No active account found with the given credentials': 'Неверные учётные данные',
    'Token is invalid or expired': 'Токен недействителен или истёк',
    'Given token not valid for any token type': 'Токен недействителен',
    'Post not found': 'Пост не найден',
}


def translate_errors(data):
    """Rekursiv ravishda xato xabarlarini tarjima qilish"""
    if isinstance(data, dict):
        return {k: translate_errors(v) for k, v in data.items()}
    if isinstance(data, list):
        return [translate_errors(i) for i in data]
    if isinstance(data, str) and data in RU_TRANSLATIONS:
        return RU_TRANSLATIONS[data]
    if isinstance(data, str):
        for en, ru in RU_TRANSLATIONS.items():
            if en in data:
                return data.replace(en, ru)
    return data


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.data = translate_errors(response.data)
    return response
