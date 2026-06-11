"""GPS koordinatalar uchun umumiy DecimalField parametrlari va masofa hisobi."""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Union

# Oldin: max_digits=10, decimal_places=7
# Hozir: 18 kasr (mobil GPS to‘liq aniqlik)
GEO_COORD_MAX_DIGITS = 21
GEO_COORD_DECIMAL_PLACES = 18

Coord = Union[Decimal, float, int, str]


def haversine_distance_m(lat1: Coord, lon1: Coord, lat2: Coord, lon2: Coord) -> float:
    """Ikki nuqta orasidagi masofa (metr)."""
    lat1_f, lon1_f = float(lat1), float(lon1)
    lat2_f, lon2_f = float(lat2), float(lon2)
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1_f), math.radians(lat2_f)
    dphi = math.radians(lat2_f - lat1_f)
    dlambda = math.radians(lon2_f - lon1_f)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def is_within_radius_m(
    *,
    point_lat: Coord,
    point_lon: Coord,
    center_lat: Coord,
    center_lon: Coord,
    radius_m: Union[int, float, Decimal],
) -> bool:
    return haversine_distance_m(point_lat, point_lon, center_lat, center_lon) <= float(radius_m)
