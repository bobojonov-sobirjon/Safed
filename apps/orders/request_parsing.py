"""
Normalize order checkout body from JSON or multipart/form-data (Swagger Try it out).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Union

from django.http import QueryDict


def _parse_json_value(raw: str) -> Any:
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Swagger/curl: two objects separated by comma without [] — wrap as array
        if text.startswith('{') and not text.startswith('['):
            try:
                return json.loads(f'[{text}]')
            except json.JSONDecodeError:
                pass
        raise


def normalize_products_data(value: Any) -> List[Dict[str, Any]]:
    """
    Accept:
    - list of dicts (application/json)
    - one dict
    - JSON string of object or array (multipart -F)
    - multiple form values getlist('products_data')
    """
    if value is None:
        return []

    if isinstance(value, list):
        out: List[Dict[str, Any]] = []
        for item in value:
            out.extend(normalize_products_data(item))
        return out

    if isinstance(value, dict):
        return [value]

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = _parse_json_value(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                'products_data: неверный JSON. Используйте массив: '
                '[{"product_id":1,"quantity":"1","product_unit":"piece"}, ...]'
            ) from exc
        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        raise ValueError('products_data must be object or array of objects')

    raise ValueError('products_data must be a list of line items')


def _coerce_optional_int(data: Dict[str, Any], key: str) -> None:
    if key not in data:
        return
    val = data[key]
    if val is None or val == '':
        data.pop(key, None)
        return
    if isinstance(val, str) and val.strip().isdigit():
        data[key] = int(val.strip())


def _coerce_bool(data: Dict[str, Any], key: str) -> None:
    if key not in data:
        return
    val = data[key]
    if isinstance(val, bool):
        return
    if isinstance(val, str):
        data[key] = val.strip().lower() in ('true', '1', 'yes', 'y', 'on')


def parse_order_request_data(data: Union[QueryDict, Dict[str, Any]]) -> Dict[str, Any]:
    """Build serializer input from request.data (JSON or multipart)."""
    if isinstance(data, QueryDict):
        payload: Dict[str, Any] = {}
        for key in data.keys():
            if key == 'products_data' or key.startswith('products_data['):
                continue
            payload[key] = data.get(key)
        if 'products_data' in data:
            payload['products_data'] = normalize_products_data(data.getlist('products_data'))
        elif any(k.startswith('products_data[') for k in data.keys()):
            # DRF-style nested form: products_data[0][product_id]=...
            nested = data.dict()
            if 'products_data' in nested and isinstance(nested['products_data'], list):
                payload['products_data'] = nested['products_data']
    else:
        payload = dict(data)
        if 'products_data' in payload:
            payload['products_data'] = normalize_products_data(payload['products_data'])

    _coerce_optional_int(payload, 'delivery_address_id')
    _coerce_optional_int(payload, 'loyalty_points_to_use')
    _coerce_bool(payload, 'leave_at_door')

    return payload
