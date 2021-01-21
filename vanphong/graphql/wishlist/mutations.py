import graphene
from django.core.exceptions import ValidationError

from ...room.error_codes import RoomErrorCode
from ...room.utils import get_rooms_ids_without_variants
from ..core.mutations import BaseMutation
from ..core.types.common import WishlistError
from ..room.types import Room, RoomVariant
from .resolvers import resolve_wishlist_from_info
from .types import WishlistItem


class _BaseWishlistMutation(BaseMutation):
    wishlist = graphene.List(
        WishlistItem, description="The wishlist of the current user."
    )

    class Meta:
        abstract = True

    @classmethod
    def check_permissions(cls, context):
        return context.user.is_authenticated


class _BaseWishlistRoomMutation(_BaseWishlistMutation):
    class Meta:
        abstract = True

    class Arguments:
        room_id = graphene.ID(description="The ID of the room.", required=True)


class WishlistAddRoomMutation(_BaseWishlistRoomMutation):
    class Meta:
        description = "Add room to the current user's wishlist."
        error_type_class = WishlistError
        error_type_field = "wishlist_errors"

    @classmethod
    def perform_mutation(cls, _root, info, room_id):  # pylint: disable=W0221
        wishlist = resolve_wishlist_from_info(info)
        room = cls.get_node_or_error(
            info, room_id, only_type=Room, field="room_id"
        )
        cls.clean_rooms([room])
        wishlist.add_room(room)
        wishlist_items = wishlist.items.all()
        return WishlistAddRoomMutation(wishlist=wishlist_items)

    @classmethod
    def clean_rooms(cls, rooms):
        rooms_ids_without_variants = get_rooms_ids_without_variants(rooms)
        if rooms_ids_without_variants:
            raise ValidationError(
                {
                    "rooms": ValidationError(
                        "Cannot manage rooms without variants.",
                        code=RoomErrorCode.CANNOT_MANAGE_ROOM_WITHOUT_VARIANT,
                        params={"rooms": rooms_ids_without_variants},
                    )
                }
            )


class WishlistRemoveRoomMutation(_BaseWishlistRoomMutation):
    class Meta:
        description = "Remove room from the current user's wishlist."
        error_type_class = WishlistError
        error_type_field = "wishlist_errors"

    @classmethod
    def perform_mutation(cls, _root, info, room_id):  # pylint: disable=W0221
        wishlist = resolve_wishlist_from_info(info)
        room = cls.get_node_or_error(
            info, room_id, only_type=Room, field="room_id"
        )
        wishlist.remove_room(room)
        wishlist_items = wishlist.items.all()
        return WishlistRemoveRoomMutation(wishlist=wishlist_items)


class _BaseWishlistVariantMutation(_BaseWishlistMutation):
    class Meta:
        abstract = True

    class Arguments:
        variant_id = graphene.ID(
            description="The ID of the room variant.", required=True
        )


class WishlistAddRoomVariantMutation(_BaseWishlistVariantMutation):
    class Meta:
        description = "Add room variant to the current user's wishlist."
        error_type_class = WishlistError
        error_type_field = "wishlist_errors"

    @classmethod
    def perform_mutation(cls, _root, info, variant_id):  # pylint: disable=W0221
        wishlist = resolve_wishlist_from_info(info)
        variant = cls.get_node_or_error(
            info, variant_id, only_type=RoomVariant, field="variant_id"
        )
        wishlist.add_variant(variant)
        wishlist_items = wishlist.items.all()
        return WishlistAddRoomVariantMutation(wishlist=wishlist_items)


class WishlistRemoveRoomVariantMutation(_BaseWishlistVariantMutation):
    class Meta:
        description = "Remove room variant from the current user's wishlist."
        error_type_class = WishlistError
        error_type_field = "wishlist_errors"

    @classmethod
    def perform_mutation(cls, _root, info, variant_id):  # pylint: disable=W0221
        wishlist = resolve_wishlist_from_info(info)
        variant = cls.get_node_or_error(
            info, variant_id, only_type=RoomVariant, field="variant_id"
        )
        wishlist.remove_variant(variant)
        wishlist_items = wishlist.items.all()
        return WishlistRemoveRoomVariantMutation(wishlist=wishlist_items)
