import json
from django.http import QueryDict
from django.test import SimpleTestCase

from apps.orders.request_parsing import normalize_products_data, parse_order_request_data


class RequestParsingTests(SimpleTestCase):
    def test_multipart_json_object_string(self):
        qd = QueryDict(mutable=True)
        qd['products_data'] = json.dumps({'product_id': 28, 'quantity': '1', 'product_unit': 'piece'})
        qd['payment_type'] = 'cash'
        body = parse_order_request_data(qd)
        self.assertEqual(len(body['products_data']), 1)
        self.assertEqual(body['products_data'][0]['product_id'], 28)

    def test_json_array_string(self):
        raw = '[{"product_id": 5}, {"product_id": 6}]'
        self.assertEqual(len(normalize_products_data(raw)), 2)

    def test_comma_separated_objects_without_brackets(self):
        raw = """{
  "product_id": 28,
  "quantity": "2",
  "product_unit": "piece"
},
{
  "product_id": 27,
  "quantity": "1",
  "product_unit": "piece"
}"""
        items = normalize_products_data(raw)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['product_id'], 28)
        self.assertEqual(items[1]['product_id'], 27)

    def test_empty_delivery_address_removed(self):
        qd = QueryDict(mutable=True)
        qd['delivery_address_id'] = ''
        body = parse_order_request_data(qd)
        self.assertNotIn('delivery_address_id', body)
