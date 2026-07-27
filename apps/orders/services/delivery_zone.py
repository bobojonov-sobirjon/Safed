"""
Yetkazish zonasi (omborxona / sklad) tekshiruvi.

Admin panel sklad markazi (lat/long) va radius (km) saqlaydi.
Mijoz manzili Haversine bo‘yicha shu doira ichida bo‘lishi kerak.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Sequence, Tuple, Union

from apps.core.geo import (
    haversine_distance_km,
    haversine_distance_m,
    is_within_radius_m,
    m_to_km,
)
from apps.orders.models import DeliveryZone

Coord = Union[Decimal, float, int, str]


@dataclass(frozen=True)
class ZoneMatchResult:
    """Natija: mijoz manzili zona(lar) ichidami."""

    allowed: bool
    message: str
    matched_zone_id: Optional[int] = None
    nearest_zone_id: Optional[int] = None
    distance_m: Optional[float] = None
    distance_km: Optional[float] = None

    def as_dict(self) -> dict:
        return {
            'allowed': self.allowed,
            'message': self.message,
            'matched_zone_id': self.matched_zone_id,
            'nearest_zone_id': self.nearest_zone_id,
            'distance_m': self.distance_m,
            'distance_km': self.distance_km,
        }


def get_active_delivery_zones():
    return DeliveryZone.objects.filter(is_active=True).order_by('id')


def point_in_circle(
    *,
    customer_lat: Coord,
    customer_lon: Coord,
    warehouse_lat: Coord,
    warehouse_lon: Coord,
    radius_m: Union[int, float, Decimal],
) -> Tuple[bool, float]:
    """
    Bitta doira tekshiruvi.
    Returns: (inside, distance_m)
    """
    distance_m = haversine_distance_m(
        customer_lat, customer_lon, warehouse_lat, warehouse_lon
    )
    return distance_m <= float(radius_m), distance_m


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
    zones = list(get_active_delivery_zones())
    if not zones or lat is None or lon is None:
        return None
    best: Optional[Tuple[int, float]] = None
    for zone in zones:
        dist = haversine_distance_m(lat, lon, zone.lat, zone.long)
        if best is None or dist < best[1]:
            best = (zone.pk, dist)
    return best


def check_customer_in_zones(
    customer_lat: Coord,
    customer_lon: Coord,
    *,
    zones: Optional[Sequence[DeliveryZone]] = None,
) -> ZoneMatchResult:
    """
    Mijoz koordinatasini faol sklad zonalariga nisbatan tekshiradi.

    - Zona yo‘q → allowed (cheklov yo‘q)
    - Birorta zona ichida → allowed + matched_zone_id
    - Hech birida emas → allowed=False + eng yaqin zona masofasi
    """
    active = list(zones) if zones is not None else list(get_active_delivery_zones())
    if not active:
        return ZoneMatchResult(allowed=True, message='')

    nearest_id: Optional[int] = None
    nearest_m: Optional[float] = None
    matched_id: Optional[int] = None

    for zone in active:
        inside, distance_m = point_in_circle(
            customer_lat=customer_lat,
            customer_lon=customer_lon,
            warehouse_lat=zone.lat,
            warehouse_lon=zone.long,
            radius_m=zone.radius_m,
        )
        if nearest_m is None or distance_m < nearest_m:
            nearest_m = distance_m
            nearest_id = zone.pk
        if inside and matched_id is None:
            matched_id = zone.pk

    if matched_id is not None:
        assert nearest_m is not None
        return ZoneMatchResult(
            allowed=True,
            message='',
            matched_zone_id=matched_id,
            nearest_zone_id=nearest_id,
            distance_m=round(nearest_m, 2),
            distance_km=round(m_to_km(nearest_m), 3),
        )

    assert nearest_m is not None
    return ZoneMatchResult(
        allowed=False,
        message='Адрес вне зоны доставки. Выберите другой адрес или измените местоположение.',
        matched_zone_id=None,
        nearest_zone_id=nearest_id,
        distance_m=round(nearest_m, 2),
        distance_km=round(m_to_km(nearest_m), 3),
    )


def check_point_against_warehouse(
    *,
    customer_lat: Coord,
    customer_lon: Coord,
    warehouse_lat: Coord,
    warehouse_lon: Coord,
    radius_km: Union[int, float, Decimal],
) -> ZoneMatchResult:
    """
    DB ga bog‘lanmasdan: bitta sklad markazi + radius_km vs mijoz nuqtasi.
    Frontend preview / ad-hoc tekshiruv uchun.
    """
    radius_m = float(radius_km) * 1000.0
    inside, distance_m = point_in_circle(
        customer_lat=customer_lat,
        customer_lon=customer_lon,
        warehouse_lat=warehouse_lat,
        warehouse_lon=warehouse_lon,
        radius_m=radius_m,
    )
    distance_km = haversine_distance_km(
        customer_lat, customer_lon, warehouse_lat, warehouse_lon
    )
    if inside:
        return ZoneMatchResult(
            allowed=True,
            message='',
            distance_m=round(distance_m, 2),
            distance_km=round(distance_km, 3),
        )
    return ZoneMatchResult(
        allowed=False,
        message='Адрес вне зоны доставки.',
        distance_m=round(distance_m, 2),
        distance_km=round(distance_km, 3),
    )
