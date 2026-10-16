"""Pagination helper for envelope responses."""
from __future__ import annotations

from django.core.paginator import EmptyPage, Paginator

MAX_PAGE_SIZE = 100


def paginate(queryset, params, serializer=lambda obj: obj):
    try:
        page = max(int(params.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(int(params.get("page_size", 20)), MAX_PAGE_SIZE)
    except (TypeError, ValueError):
        page_size = 20
    paginator = Paginator(queryset, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)
    return {
        "items": [serializer(obj) for obj in page_obj],
        "page": page_obj.number,
        "page_size": page_size,
        "total_pages": paginator.num_pages,
        "total_count": paginator.count,
    }
