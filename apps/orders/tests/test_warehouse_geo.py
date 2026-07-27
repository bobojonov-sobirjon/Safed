"""Haversine + warehouse radius validation."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.geo import (
    haversine_distance_km,
    is_within_radius_km,
    km_to_m,
    validate_latitude,
)
from apps.orders.models import DeliveryZone
from apps.orders.serializers import DeliveryZoneSerializer
from apps.orders.services.delivery_zone import (
    check_customer_in_zones,
    check_point_against_warehouse,
)

User = get_user_model()


class GeoHaversineTests(TestCase):
    def test_same_point_zero_distance(self):
        self.assertAlmostEqual(
            haversine_distance_km(41.311, 69.240, 41.311, 69.240),
            0.0,
            places=5,
        )

    def test_within_10km_tashkent(self):
        # ~1.1 km from center
        self.assertTrue(
            is_within_radius_km(
                point_lat=41.320,
                point_lon=69.240,
                center_lat=41.311,
                center_lon=69.240,
                radius_km=10,
            )
        )

    def test_outside_radius(self):
        self.assertFalse(
            is_within_radius_km(
                point_lat=40.0,
                point_lon=70.0,
                center_lat=41.311,
                center_lon=69.240,
                radius_km=10,
            )
        )

    def test_invalid_latitude(self):
        with self.assertRaises(ValueError):
            validate_latitude(91)

    def test_km_to_m(self):
        self.assertEqual(km_to_m(10), 10_000)
        self.assertEqual(km_to_m(Decimal('0.5')), 500)


class DeliveryZoneSerializerTests(TestCase):
    def test_accepts_frontend_km_payload(self):
        ser = DeliveryZoneSerializer(
            data={
                'name': 'Asosiy sklad',
                'latitude': '41.311081',
                'longitude': '69.240562',
                'radius_km': '10',
                'is_active': True,
            }
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        obj = ser.save()
        self.assertEqual(obj.radius_m, 10_000)
        self.assertEqual(obj.lat, Decimal('41.311081'))
        out = DeliveryZoneSerializer(obj).data
        self.assertEqual(out['radius_km_display'], 10.0)

    def test_rejects_bad_coordinates(self):
        ser = DeliveryZoneSerializer(
            data={
                'latitude': '99',
                'longitude': '69.24',
                'radius_km': '5',
            }
        )
        self.assertFalse(ser.is_valid())


class WarehouseCheckServiceTests(TestCase):
    def setUp(self):
        DeliveryZone.objects.create(
            name='Markaz',
            address='Toshkent',
            lat=Decimal('41.311081'),
            long=Decimal('69.240562'),
            radius_m=10_000,
            is_active=True,
        )

    def test_check_customer_inside(self):
        result = check_customer_in_zones(Decimal('41.312'), Decimal('69.241'))
        self.assertTrue(result.allowed)
        self.assertIsNotNone(result.matched_zone_id)

    def test_check_customer_outside(self):
        result = check_customer_in_zones(Decimal('40.0'), Decimal('70.0'))
        self.assertFalse(result.allowed)
        self.assertIsNotNone(result.distance_km)

    def test_ad_hoc_preview(self):
        result = check_point_against_warehouse(
            customer_lat=41.312,
            customer_lon=69.241,
            warehouse_lat=41.311081,
            warehouse_lon=69.240562,
            radius_km=10,
        )
        self.assertTrue(result.allowed)


class WarehousePreviewApiTests(TestCase):
    def setUp(self):
        group, _ = Group.objects.get_or_create(name='Admin')
        self.user = User.objects.create_user(phone='+998901230011', password='pass')
        self.user.groups.add(group)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_preview_endpoint(self):
        resp = self.client.post(
            '/api/v1/admin/delivery-zones/preview/',
            {
                'warehouse_latitude': '41.311081',
                'warehouse_longitude': '69.240562',
                'radius_km': '10',
                'customer_latitude': '41.312',
                'customer_longitude': '69.241',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['allowed'])
        self.assertIn('distance_km', resp.data)

    def test_create_zone_with_km(self):
        resp = self.client.post(
            '/api/v1/admin/delivery-zones/',
            {
                'name': 'Sklad 1',
                'latitude': '41.311081',
                'longitude': '69.240562',
                'radius_km': '10',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['radius_m'], 10000)
        self.assertEqual(resp.data['radius_km_display'], 10.0)
