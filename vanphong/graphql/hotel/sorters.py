import graphene

from ..core.types import SortInputObjectType


class HotelSortField(graphene.Enum):
    NAME = ["name", "slug"]

    @property
    def description(self):
        if self.name in HotelSortField.__enum__._member_names_:
            sort_name = self.name.lower().replace("_", " ")
            return f"Sort hotels by {sort_name}."
        raise ValueError("Unsupported enum value: %s" % self.value)


class HotelSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = HotelSortField
        type_name = "hotels"
