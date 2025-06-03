# https://docs.djangoproject.com/en/3.2/topics/pagination/
import math
from django.core.paginator import Paginator


def make_pagination_range(page_range, qty_pages, current_page):
    total_pages = len(page_range)

    # Se o total de páginas for menor ou igual à quantidade desejada, retorna todas
    if total_pages <= 3:
        return {
            "pagination": list(page_range),
            "page_range": page_range,
            "qty_pages": qty_pages,
            "current_page": current_page,
            "total_pages": total_pages,
            "start_range": 0,
            "stop_range": total_pages,
            "first_page_out_of_range": False,
            "last_page_out_of_range": False,
        }

    middle_range = math.ceil(qty_pages / 2)
    start_range = max(current_page - middle_range, 0)
    stop_range = min(current_page + middle_range, total_pages)

    if stop_range - start_range < qty_pages:
        start_range = max(stop_range - qty_pages, 0)

    return {
        "pagination": list(page_range[start_range:stop_range]),
        "page_range": page_range,
        "qty_pages": qty_pages,
        "current_page": current_page,
        "total_pages": total_pages,
        "start_range": start_range,
        "stop_range": stop_range,
        "first_page_out_of_range": start_range > 0,
        "last_page_out_of_range": stop_range < total_pages,
    }


def make_pagination(request, queryset, per_page, qty_pages=3):
    try:
        current_page = int(request.GET.get("page", 1))
    except ValueError:
        current_page = 1

    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(current_page)

    pagination_range = make_pagination_range(
        paginator.page_range, qty_pages, current_page
    )

    return page_obj, pagination_range
