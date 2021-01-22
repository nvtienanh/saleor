import django_filters

from ...place.models import Place
from ..core.types import FilterInputObjectType
from ..utils.filters import filter_by_query_param


def filter_place_search(qs, _, value):
    place_fields = [
        "name",
        "province"
    ]
    qs = filter_by_query_param(qs, value, place_fields)
    return qs


class PlaceFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method=filter_place_search)

    class Meta:
        model = Place
        fields = ["search"]


class PlaceFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = PlaceFilter
