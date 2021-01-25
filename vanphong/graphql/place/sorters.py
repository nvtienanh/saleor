import graphene
from django.db.models import Count, QuerySet

from ..core.types import SortInputObjectType


class PlaceSortField(graphene.Enum):
    NAME = ["name", "pk"]
    ITEMS_COUNT = ["items_count", "name", "pk"]

    @property
    def description(self):
        if self.name in PlaceSortField.__enum__._member_names_:
            sort_name = self.name.lower().replace("_", " ")
            return f"Sort places by {sort_name}."
        raise ValueError("Unsupported enum value: %s" % self.value)

    @staticmethod
    def qs_with_items_count(queryset: QuerySet) -> QuerySet:
        return queryset.annotate(items_count=Count("items__id"))


class PlaceSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = PlaceSortField
        type_name = "places"
