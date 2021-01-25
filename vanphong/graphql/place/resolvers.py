import graphene

from ...place import models
from ..core.validators import validate_one_of_args_is_in_query
from ..utils.filters import filter_by_query_param
from .types import Place

PLACE_SEARCH_FIELDS = ("name",)


def resolve_place(info, place_id=None, name=None):
    validate_one_of_args_is_in_query("id", place_id, "name", name)
    if place_id:
        return graphene.Node.get_node_from_global_id(info, place_id, Place)
    if name:
        return models.Place.objects.filter(name=name).first()


def resolve_places(info, query, **_kwargs):
    qs = models.Place.objects.all()
    return filter_by_query_param(qs, query, PLACE_SEARCH_FIELDS)
