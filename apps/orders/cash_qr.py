"""Cash delivery QR PNG (qrcode package) — media fayl sifatida saqlash."""
from __future__ import annotations

import io

import qrcode
from django.core.files.base import ContentFile
from qrcode.constants import ERROR_CORRECT_M


def render_cash_qr_png(payload: str, *, box_size: int = 10) -> bytes:
    """Encode payload (cash_qr_token) as PNG bytes."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def render_cash_qr_file(payload: str, *, filename: str) -> ContentFile:
    """Django ImageField uchun PNG ContentFile."""
    return ContentFile(render_cash_qr_png(payload), name=filename)
