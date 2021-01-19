import graphene

from .mutations import (
    WishlistAddRoomMutation,
    WishlistAddRoomVariantMutation,
    WishlistRemoveRoomMutation,
    WishlistRemoveRoomVariantMutation,
)

# User's wishlist queries are located in the "saleor.graphql.account" module:
#
#     me {
#         wishlist
#     }


class WishlistMutations(graphene.ObjectType):
    wishlist_add_room = WishlistAddRoomMutation.Field()
    wishlist_remove_room = WishlistRemoveRoomMutation.Field()
    wishlist_add_variant = WishlistAddRoomVariantMutation.Field()
    wishlist_remove_variant = WishlistRemoveRoomVariantMutation.Field()
