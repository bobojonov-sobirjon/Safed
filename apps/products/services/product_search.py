"""
Mahsulot qidiruv — barcha tillar (uz, ru, en) bo'yicha.
App tili qanday bo'lishidan qat'iy nazar, ruscha nom bilan qidirilsa ham topiladi.
"""
from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.products.models import Products


def filter_products_by_query(qs: QuerySet, query: str) -> QuerySet:
    """Filter product queryset by search term across all translation languages."""
    q = (query or '').strip()
    if not q:
        return qs

    search_ids = (
        Products.objects.language('all')
        .filter(
            Q(unique_id__icontains=q)
            | Q(barcodes__barcode__icontains=q)
            | Q(translations__name__icontains=q)
            | Q(translations__description__icontains=q)
            | Q(translations__composition__icontains=q)
        )
        .values_list('pk', flat=True)
        .distinct()
    )
    return qs.filter(pk__in=search_ids)
