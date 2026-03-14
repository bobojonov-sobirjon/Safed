"""
Application-wide enums and constants.
"""
from enum import Enum
from typing import List, Tuple


class OrderStatus(str, Enum):
    """Order status choices."""
    PENDING = 'pending'
    PROCESS = 'process'
    DELIVERING = 'delivering'
    COMPLETED = 'completed'
    REJECTED = 'rejected'
    
    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        return [
            (cls.PENDING.value, 'В ожидании'),
            (cls.PROCESS.value, 'В обработке'),
            (cls.DELIVERING.value, 'Доставляется'),
            (cls.COMPLETED.value, 'Выполнен'),
            (cls.REJECTED.value, 'Отменён'),
        ]
    
    @classmethod
    def active_statuses(cls) -> List[str]:
        return [cls.PENDING.value, cls.PROCESS.value, cls.DELIVERING.value]
    
    @classmethod
    def final_statuses(cls) -> List[str]:
        return [cls.COMPLETED.value, cls.REJECTED.value]


class UserGroup(str, Enum):
    """User group names."""
    USER = 'User'
    SUPER_ADMIN = 'Super Admin'
    ADMIN = 'Admin'
    OPERATOR = 'Operator'
    COURIER = 'Courier'
    
    @classmethod
    def staff_groups(cls) -> List[str]:
        return [cls.SUPER_ADMIN.value, cls.ADMIN.value, cls.OPERATOR.value, cls.COURIER.value]
    
    @classmethod
    def admin_groups(cls) -> List[str]:
        return [cls.SUPER_ADMIN.value, cls.ADMIN.value]


class DeviceType(str, Enum):
    """Device types for push notifications."""
    ANDROID = 'android'
    IOS = 'ios'
    WEB = 'web'
    
    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        return [
            (cls.ANDROID.value, 'Android'),
            (cls.IOS.value, 'iOS'),
            (cls.WEB.value, 'Web'),
        ]


class Language(str, Enum):
    """Supported languages."""
    RU = 'ru'
    UZ = 'uz'
    EN = 'en'
    
    @classmethod
    def codes(cls) -> List[str]:
        return [cls.RU.value, cls.UZ.value, cls.EN.value]
