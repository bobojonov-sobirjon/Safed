from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import UserDevice

User = get_user_model()


class UserDeviceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='998901111111', password='pass12345')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = '/api/v1/devices/'

    def test_post_creates_device(self):
        resp = self.client.post(
            self.url,
            {'device_token': 'tok-abc', 'device_type': 'android'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['is_active'])
        self.assertEqual(UserDevice.objects.filter(user=self.user).count(), 1)

    def test_post_same_token_updates(self):
        self.client.post(self.url, {'device_token': 'tok-abc', 'device_type': 'android'}, format='json')
        resp = self.client.post(self.url, {'device_token': 'tok-abc', 'device_type': 'ios'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['device_type'], 'ios')
        self.assertEqual(UserDevice.objects.filter(user=self.user).count(), 1)

    def test_get_lists_own_devices(self):
        UserDevice.objects.create(user=self.user, device_token='a', device_type='android')
        other = User.objects.create_user(phone='998902222222', password='pass12345')
        UserDevice.objects.create(user=other, device_token='b', device_type='ios')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['device_token'], 'a')

    def test_put_updates_type(self):
        UserDevice.objects.create(user=self.user, device_token='tok-abc', device_type='android')
        resp = self.client.put(
            self.url,
            {'device_token': 'tok-abc', 'device_type': 'ios'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['device_type'], 'ios')

    def test_patch_is_active(self):
        UserDevice.objects.create(user=self.user, device_token='tok-abc', device_type='android')
        resp = self.client.patch(
            self.url,
            {'device_token': 'tok-abc', 'is_active': False},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['is_active'])
