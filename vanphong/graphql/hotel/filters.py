import django_filters
from graphene_django.filter import GlobalIDMultipleChoiceFilter

from ...hotel.models import Stock, Hotel
from ..core.types import FilterInputObjectType
from ..utils.filters import filter_by_query_param


def prefech_qs_for_filter(qs):
    return qs.prefetch_related("address")


def filter_search_hotel(qs, _, value):
    search_fields = [
        "name",
        "company_name",
        "email",
        "address__street_address_1",
        "address__street_address_2",
        "address__city",
        "address__postal_code",
        "address__phone",
    ]

    if value:
        qs = prefech_qs_for_filter(qs)
        qs = filter_by_query_param(qs, value, search_fields)
    return qs


def filter_search_stock(qs, _, value):
    search_fields = [
        "room_variant__room__name",
        "room_variant__name",
        "hotel__name",
        "hotel__company_name",
    ]
    if value:
        qs = qs.select_related("room_variant", "hotel").prefetch_related(
            "room_variant__room"
        )
        qs = filter_by_query_param(qs, value, search_fields)
    return qs


class HotelFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method=filter_search_hotel)
    ids = GlobalIDMultipleChoiceFilter(field_name="id")

    class Meta:
        model = Hotel
        fields = []


class HotelFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = HotelFilter


class StockFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method=filter_search_stock)

    class Meta:
        model = Stock
        fields = ["quantity"]


class StockFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = StockFilter
