"""
Yetkazish zonasi tekshiruvi: faol zonalar ichida bo'lishi kerak.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Tuple

from apps.core.geo import is_within_radius_m
from apps.orders.models import DeliveryZone


def get_active_delivery_zones():
    return DeliveryZone.objects.filter(is_active=True).order_by('id')


def is_location_in_delivery_zone(lat, lon) -> bool:
    """True if point is inside any active zone, or no zones configured."""
    zones = list(get_active_delivery_zones())
    if not zones:
        return True
    if lat is None or lon is None:
        return False
    for zone in zones:
        if is_within_radius_m(
            point_lat=lat,
            point_lon=lon,
            center_lat=zone.lat,
            center_lon=zone.long,
            radius_m=zone.radius_m,
        ):
            return True
    return False


def validate_delivery_location(lat, lon) -> Optional[str]:
    """
    Return error message if location is outside all active zones.
    None means OK.
    """
    zones = list(get_active_delivery_zones())
    if not zones:
        return None
    if lat is None or lon is None:
        return 'Укажите координаты доставки (lat, long).'
    if is_location_in_delivery_zone(lat, lon):
        return None
    return 'Адрес вне зоны доставки. Выберите другой адрес или измените местоположение.'


def nearest_zone_distance_m(lat, lon) -> Optional[Tuple[int, float]]:
    """(zone_id, distance_m) to closest active zone center, or None if no zones."""
    from apps.core.geo import haversine_distance_m

    zones = list(get_active_delivery_zones())
    if not zones or lat is None or lon is None:
        return None
    best = None
    for zone in zones:
        dist = haversine_distance_m(lat, lon, zone.lat, zone.long)
        if best is None or dist < best[1]:
            best = (zone.pk, dist)
    return best
