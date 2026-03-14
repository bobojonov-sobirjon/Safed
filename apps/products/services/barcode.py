"""Barcode image yaratish"""
import io
import os
import uuid
from django.core.files.base import ContentFile
from django.conf import settings

try:
    import barcode
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False


def generate_barcode_number():
    """Unique barcode string (faqat raqamlar, Code128 uchun)"""
    return str(uuid.uuid4().int)[:12].zfill(12)


def generate_barcode_image(barcode_number: str) -> ContentFile | None:
    """
    Barcode rasmini yaratish. ContentFile qaytaradi (Django ImageField uchun).
    """
    if not BARCODE_AVAILABLE:
        return None
    try:
        BC = barcode.get_barcode_class('code128')
        code = BC(barcode_number, writer=ImageWriter())
        buffer = io.BytesIO()
        code.write(buffer)
        buffer.seek(0)
        return ContentFile(buffer.getvalue(), name=f'{barcode_number}.png')
    except Exception:
        return None
