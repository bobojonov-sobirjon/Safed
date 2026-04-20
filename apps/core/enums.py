"""
Application-wide enums and constants.
"""
from enum import Enum
from typing import List, Tuple


class OrderStatus(str, Enum):
    """Order status choices."""
    NEW = 'new'                 # yangi
    PICKING = 'picking'         # yig'ilyapti
    ON_THE_WAY = 'on_the_way'   # yo'lda
    DELIVERED = 'delivered'     # yetkazildi
    REJECTED = 'rejected'       # bekor (admin/operator)
    CANCELLED = 'cancelled'     # bekor (user)
    
    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        return [
            (cls.NEW.value, 'Yangi'),
            (cls.PICKING.value, 'Yig‘ilyapti'),
            (cls.ON_THE_WAY.value, 'Yo‘lda'),
            (cls.DELIVERED.value, 'Yetkazildi'),
            (cls.REJECTED.value, 'Отменён'),
            (cls.CANCELLED.value, 'Отменён пользователем'),
        ]
    
    @classmethod
    def active_statuses(cls) -> List[str]:
        return [cls.NEW.value, cls.PICKING.value, cls.ON_THE_WAY.value]
    
    @classmethod
    def final_statuses(cls) -> List[str]:
        return [cls.DELIVERED.value, cls.REJECTED.value, cls.CANCELLED.value]


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
