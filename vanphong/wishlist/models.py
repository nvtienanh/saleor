import uuid

from django.db import models, transaction

from ..account.models import User
from ..room.models import Room, RoomVariant


class Wishlist(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(
        User, related_name="wishlist", on_delete=models.CASCADE, blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def set_user(self, user):
        self.user = user
        self.save()

    def get_all_variants(self):
        return RoomVariant.objects.filter(
            wishlist_items__wishlist_id=self.pk
        ).distinct()

    def add_room(self, room: Room):
        item, _is_created = self.items.get_or_create(room_id=room.pk)
        return item

    def remove_room(self, room: Room):
        self.items.filter(room_id=room.pk).delete()

    def add_variant(self, variant: RoomVariant):
        item, _is_created = self.items.get_or_create(room_id=variant.room_id)
        item.variants.add(variant)
        return item

    def remove_variant(self, variant: RoomVariant):
        try:
            item = self.items.get(room_id=variant.room_id)
        except WishlistItem.DoesNotExist:
            return
        else:
            item.variants.remove(variant)
            # If it was the last variant, delete the whole item
            if item.variants.count() == 0:
                item.delete()


class WishlistItemQuerySet(models.QuerySet):
    @transaction.atomic()
    def move_items_between_wishlists(self, src_wishlist, dst_wishlist):
        dst_wishlist_map = {}
        for dst_item in dst_wishlist.items.all():
            dst_wishlist_map[dst_item.room_id] = dst_item
        # Copying the items from the source to the destination wishlist.
        for src_item in src_wishlist.items.all():
            if src_item.room_id in dst_wishlist_map:
                # This wishlist item's room already exist.
                # Adding and the variants, "add" already handles duplicates.
                dst_item = dst_wishlist_map[src_item.room_id]
                dst_item.variants.add(*src_item.variants.all())
                src_item.delete()
            else:
                # This wishlist item contains a new room.
                # It can be reassigned to the destination wishlist.
                src_item.wishlist = dst_wishlist
                src_item.save()
        self.filter(wishlist=src_wishlist).update(wishlist=dst_wishlist)


class WishlistItem(models.Model):
    wishlist = models.ForeignKey(
        Wishlist, related_name="items", on_delete=models.CASCADE
    )
    room = models.ForeignKey(
        Room, related_name="wishlist_items", on_delete=models.CASCADE
    )
    variants = models.ManyToManyField(
        RoomVariant, related_name="wishlist_items", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = WishlistItemQuerySet.as_manager()

    class Meta:
        unique_together = ("wishlist", "room")

    def __str__(self):
        return "WishlistItem (%s, %s)" % (self.wishlist.user, self.room)
