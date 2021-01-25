import graphene

from ...core.permissions import PlacePermissions
from ...place import models
from ..core.mutations import ModelDeleteMutation, ModelMutation
from ..core.types.common import PlaceError
from .types import Place

class PlaceInput(graphene.InputObjectType):
    name = graphene.String(description="Name of the place.")


class PlaceCreateInput(graphene.InputObjectType):
    name = graphene.String(description="Name of the place.", required=True)
    province = graphene.String(description="City name of the place.", required=True)
    place_type = graphene.String(description="Type of place.", required=True)
    country = graphene.String(description="Country of place.", required=True)
    hotels = graphene.Int(description="Number of properties.", required=True)
    featured_image = graphene.String(description="Featured image url of the place", required=True)


class PlaceCreate(ModelMutation):
    class Arguments:
        input = PlaceCreateInput(
            required=True, description="Fields required to create a place."
        )

    class Meta:
        description = "Creates a new Place."
        model = models.Place
        permissions = (PlacePermissions.MANAGE_PLACES,)
        error_type_class = PlaceError
        error_type_field = "place_errors"



class PlaceUpdate(ModelMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a place to update.")
        input = PlaceInput(
            required=True, description="Fields required to update a place."
        )

    class Meta:
        description = "Updates a place."
        model = models.Place
        permissions = (PlacePermissions.MANAGE_PLACES,)
        error_type_class = PlaceError
        error_type_field = "place_errors"



class PlaceDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a place to delete.")

    class Meta:
        description = "Deletes a place."
        model = models.Place
        permissions = (PlacePermissions.MANAGE_PLACES,)
        error_type_class = PlaceError
        error_type_field = "place_errors"
