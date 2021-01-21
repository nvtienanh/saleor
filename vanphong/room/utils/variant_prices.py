import operator
from collections import defaultdict
from functools import reduce
from typing import Optional

from django.db.models.query_utils import Q
from prices import Money

from ...discount.utils import calculate_discounted_price, fetch_active_discounts
from ..models import Room, RoomChannelListing, RoomVariantChannelListing


def _get_variant_prices_in_channels_dict(room):
    prices_dict = defaultdict(list)
    for variant_channel_listing in RoomVariantChannelListing.objects.filter(
        variant__room_id=room
    ):
        channel_id = variant_channel_listing.channel_id
        prices_dict[channel_id].append(variant_channel_listing.price)
    return prices_dict


def _get_room_discounted_price(
    variant_prices, room, collections, discounts, channel
) -> Optional[Money]:
    discounted_variants_price = []
    for variant_price in variant_prices:
        discounted_variant_price = calculate_discounted_price(
            room=room,
            price=variant_price,
            collections=collections,
            discounts=discounts,
            channel=channel,
        )
        discounted_variants_price.append(discounted_variant_price)
    return min(discounted_variants_price)


def update_room_discounted_price(room, discounts=None):
    if discounts is None:
        discounts = fetch_active_discounts()
    collections = list(room.collections.all())
    variant_prices_in_channels_dict = _get_variant_prices_in_channels_dict(room)
    changed_rooms_channels_to_update = []
    for room_channel_listing in room.channel_listings.all():
        channel_id = room_channel_listing.channel_id
        variant_prices_dict = variant_prices_in_channels_dict[channel_id]
        room_discounted_price = _get_room_discounted_price(
            variant_prices_dict,
            room,
            collections,
            discounts,
            room_channel_listing.channel,
        )
        if room_channel_listing.discounted_price != room_discounted_price:
            room_channel_listing.discounted_price_amount = (
                room_discounted_price.amount
            )
            changed_rooms_channels_to_update.append(room_channel_listing)
    RoomChannelListing.objects.bulk_update(
        changed_rooms_channels_to_update, ["discounted_price_amount"]
    )


def update_rooms_discounted_prices(rooms, discounts=None):
    if discounts is None:
        discounts = fetch_active_discounts()

    for room in rooms.prefetch_related("channel_listings"):
        update_room_discounted_price(room, discounts)


def update_rooms_discounted_prices_of_catalogues(
    room_ids=None, category_ids=None, collection_ids=None
):
    # Building the matching rooms query
    q_list = []
    if room_ids:
        q_list.append(Q(pk__in=room_ids))
    if category_ids:
        q_list.append(Q(category_id__in=category_ids))
    if collection_ids:
        q_list.append(Q(collectionroom__collection_id__in=collection_ids))
    # Asserting that the function was called with some ids
    if q_list:
        # Querying the rooms
        q_or = reduce(operator.or_, q_list)
        rooms = Room.objects.filter(q_or).distinct()

        update_rooms_discounted_prices(rooms)


def update_rooms_discounted_prices_of_discount(discount):
    update_rooms_discounted_prices_of_catalogues(
        room_ids=discount.rooms.all().values_list("id", flat=True),
        category_ids=discount.categories.all().values_list("id", flat=True),
        collection_ids=discount.collections.all().values_list("id", flat=True),
    )
