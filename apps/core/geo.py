"""
GPS utilities: coordinate validation and Haversine distance.

Earth radius uses WGS84 mean radius (6371 km). Distances are computed in meters
internally for precision; km helpers convert at the boundary.
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Union

GEO_COORD_MAX_DIGITS = 21
GEO_COORD_DECIMAL_PLACES = 18

# WGS84 mean Earth radius
EARTH_RADIUS_M = 6_371_000.0
EARTH_RADIUS_KM = 6_371.0

Coord = Union[Decimal, float, int, str]


def _as_float(value: Coord) -> float:
    return float(value)


def validate_latitude(value: Coord) -> float:
    lat = _as_float(value)
    if not math.isfinite(lat) or lat < -90.0 or lat > 90.0:
        raise ValueError('latitude must be between -90 and 90')
    return lat


def validate_longitude(value: Coord) -> float:
    lon = _as_float(value)
    if not math.isfinite(lon) or lon < -180.0 or lon > 180.0:
        raise ValueError('longitude must be between -180 and 180')
    return lon


def haversine_distance_m(lat1: Coord, lon1: Coord, lat2: Coord, lon2: Coord) -> float:
    """Great-circle distance between two WGS84 points, in meters."""
    lat1_f = validate_latitude(lat1)
    lon1_f = validate_longitude(lon1)
    lat2_f = validate_latitude(lat2)
    lon2_f = validate_longitude(lon2)

    phi1, phi2 = math.radians(lat1_f), math.radians(lat2_f)
    dphi = math.radians(lat2_f - lat1_f)
    dlambda = math.radians(lon2_f - lon1_f)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def haversine_distance_km(lat1: Coord, lon1: Coord, lat2: Coord, lon2: Coord) -> float:
    """Great-circle distance in kilometers."""
    return haversine_distance_m(lat1, lon1, lat2, lon2) / 1000.0


def is_within_radius_m(
    *,
    point_lat: Coord,
    point_lon: Coord,
    center_lat: Coord,
    center_lon: Coord,
    radius_m: Union[int, float, Decimal],
) -> bool:
    radius = float(radius_m)
    if radius < 0:
        raise ValueError('radius_m must be >= 0')
    return haversine_distance_m(point_lat, point_lon, center_lat, center_lon) <= radius


def is_within_radius_km(
    *,
    point_lat: Coord,
    point_lon: Coord,
    center_lat: Coord,
    center_lon: Coord,
    radius_km: Union[int, float, Decimal],
) -> bool:
    """True if point is inside the circle around center with given radius (km)."""
    radius = float(radius_km)
    if radius < 0:
        raise ValueError('radius_km must be >= 0')
    return is_within_radius_m(
        point_lat=point_lat,
        point_lon=point_lon,
        center_lat=center_lat,
        center_lon=center_lon,
        radius_m=radius * 1000.0,
    )


def km_to_m(radius_km: Union[int, float, Decimal]) -> int:
    """Convert km → meters (rounded to nearest meter for storage)."""
    value = float(radius_km)
    if value <= 0:
        raise ValueError('radius_km must be > 0')
    return max(1, int(round(value * 1000)))


def m_to_km(radius_m: Union[int, float, Decimal]) -> float:
    return float(radius_m) / 1000.0
