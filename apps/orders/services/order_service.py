"""
Legacy placeholder: order flows live in `apps.orders.views` and `apps.orders.pricing`.
Kept so `from apps.orders.services import OrderService` does not break.
"""


class OrderService:
    """Deprecated — use API views + `compute_order_pricing`."""

    pass
