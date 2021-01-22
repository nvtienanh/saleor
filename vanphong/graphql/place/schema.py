import graphene

from ..core.fields import FilterInputConnectionField
from .bulk_mutations import PlaceBulkDelete
from .filters import PlaceFilterInput
from .mutations import (
    PlaceCreate,
    PlaceDelete,
    PlaceUpdate,
)
from .resolvers import resolve_place, resolve_places
from .sorters import PlaceSortingInput
from .types import Place


class PlaceQueries(graphene.ObjectType):
    place = graphene.Field(
        Place,
        id=graphene.Argument(graphene.ID, description="ID of the place."),
        name=graphene.Argument(graphene.String, description="The place's name."),
        description="Look up a navigation place by ID or name.",
    )
    places = FilterInputConnectionField(
        Place,
        sort_by=PlaceSortingInput(description="Sort places."),
        filter=PlaceFilterInput(description="Filtering options for places."),
        description="List of the storefront's places.",
    )

    def resolve_place(self, info, **data):
        return resolve_place(info, data.get("id"), data.get("name"))

    def resolve_places(self, info, query=None, **kwargs):
        return resolve_places(info, query, **kwargs)


class PlaceMutations(graphene.ObjectType):
    place_create = PlaceCreate.Field()
    place_delete = PlaceDelete.Field()
    place_bulk_delete = PlaceBulkDelete.Field()
    place_update = PlaceUpdate.Field()
