import graphene

from ...core.permissions import PlacePermissions
from ...place import models
from ..core.mutations import ModelBulkDeleteMutation
from ..core.types.common import PlaceError


class PlaceBulkDelete(ModelBulkDeleteMutation):
    class Arguments:
        ids = graphene.List(
            graphene.ID, required=True, description="List of place IDs to delete."
        )

    class Meta:
        description = "Deletes places."
        model = models.Place
        permissions = (PlacePermissions.MANAGE_PLACES,)
        error_type_class = PlaceError
        error_type_field = "place_errors"
