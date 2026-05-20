"""
Application-wide enums and constants.
"""
from enum import Enum
from typing import List, Tuple


class OrderStatus(str, Enum):
    """Order lifecycle (Korzinka-style). Legacy DB values migrated: new→created, on_the_way→shipped."""

    CREATED = 'created'
    CONFIRMED = 'confirmed'
    PICKING = 'picking'
    SHIPPED = 'shipped'
    DELIVERED = 'delivered'
    COMPLETED = 'completed'
    REJECTED = 'rejected'
    CANCELLED = 'cancelled'

    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        return [
            (cls.CREATED.value, 'Created'),
            (cls.CONFIRMED.value, 'Confirmed'),
            (cls.PICKING.value, 'Picking'),
            (cls.SHIPPED.value, 'Shipped'),
            (cls.DELIVERED.value, 'Delivered'),
            (cls.COMPLETED.value, 'Completed'),
            (cls.REJECTED.value, 'Rejected'),
            (cls.CANCELLED.value, 'Cancelled (user)'),
        ]

    @classmethod
    def active_statuses(cls) -> List[str]:
        return [cls.CREATED.value, cls.CONFIRMED.value, cls.PICKING.value, cls.SHIPPED.value]

    @classmethod
    def final_statuses(cls) -> List[str]:
        return [
            cls.DELIVERED.value,
            cls.COMPLETED.value,
            cls.REJECTED.value,
            cls.CANCELLED.value,
        ]

    @classmethod
    def user_cancellable_statuses(cls) -> List[str]:
        """User may cancel only before the order is confirmed."""
        return [cls.CREATED.value]


class PaymentType(str, Enum):
    """How the customer pays at checkout."""

    CARD = 'card'
    CASH = 'cash'

    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        return [(cls.CARD.value, 'Card'), (cls.CASH.value, 'Cash')]


class PaymentStatus(str, Enum):
    """Payment lifecycle on order (checkout / PSP hook)."""

    PENDING = 'pending'
    AUTHORIZED = 'authorized'
    PAID = 'paid'
    FAILED = 'failed'
    REFUNDED = 'refunded'

    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        return [
            (cls.PENDING.value, 'Pending'),
            (cls.AUTHORIZED.value, 'Authorized'),
            (cls.PAID.value, 'Paid'),
            (cls.FAILED.value, 'Failed'),
            (cls.REFUNDED.value, 'Refunded'),
        ]


class SaleUnit(str, Enum):
    """Legacy sale type; kept in sync with ProductUnit for buffer/stock helpers."""

    PIECE = 'piece'
    WEIGHT = 'weight'

    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        return [(cls.PIECE.value, 'Piece (pcs)'), (cls.WEIGHT.value, 'Weight (kg)')]


class ProductUnit(str, Enum):
    """Catalog and cart unit for pricing."""

    PIECE = 'piece'
    KG = 'kg'
    GRAM = 'gram'
    LITER = 'liter'
    ML = 'ml'

    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        from apps.products.product_unit_specs import product_unit_choices
        return product_unit_choices()

    @classmethod
    def values(cls) -> List[str]:
        return [c[0] for c in cls.choices()]

    @classmethod
    def weight_units(cls) -> frozenset:
        return frozenset({cls.KG.value, cls.GRAM.value})

    @classmethod
    def volume_units(cls) -> frozenset:
        return frozenset({cls.LITER.value, cls.ML.value})

    @classmethod
    def fractional_units(cls) -> frozenset:
        return cls.weight_units() | cls.volume_units()

    def family(self) -> str:
        if self.value in self.weight_units():
            return 'weight'
        if self.value in self.volume_units():
            return 'volume'
        return 'piece'


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
