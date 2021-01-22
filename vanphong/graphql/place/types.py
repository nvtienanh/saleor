import graphene
from graphene import relay
from graphene_federation import key

from ...place import models
from ..core.connection import CountableDjangoObjectType


@key(fields="id")
class Place(CountableDjangoObjectType):
    class Meta:
        description = "Represents user address data."
        only_fields = [
            "name",
            "province",
            "hotels",
            "place_type",
            "country",
            "featured_image",
        ]
        interfaces = [relay.Node]
        model = models.Place
    
    @staticmethod
    def __resolve_reference(root, _info, **_kwargs):
        return graphene.Node.get_node_from_global_id(_info, root.id)
