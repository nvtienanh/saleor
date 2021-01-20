from unittest.mock import patch

from django.core.management import call_command
from prices import Money

from ..tasks import (
    update_rooms_discounted_prices_of_catalogues,
    update_rooms_discounted_prices_task,
)
from ..utils.variant_prices import update_room_discounted_price


def test_update_room_discounted_price(room, channel_USD):
    variant = room.variants.first()
    variant_channel_listing = variant.channel_listings.get(channel_id=channel_USD.id)
    room_channel_listing = room.channel_listings.get(channel_id=channel_USD.id)
    variant_channel_listing.price = Money("4.99", "USD")
    variant_channel_listing.save()
    room_channel_listing.refresh_from_db()

    assert room_channel_listing.discounted_price == Money("10", "USD")

    update_room_discounted_price(room)

    room_channel_listing.refresh_from_db()
    assert room_channel_listing.discounted_price == variant_channel_listing.price


def test_update_rooms_discounted_prices_of_catalogues_for_room(
    room, channel_USD
):
    variant = room.variants.first()
    variant_channel_listing = variant.channel_listings.get(channel_id=channel_USD.id)
    room_channel_listing = room.channel_listings.get(channel_id=channel_USD.id)
    variant_channel_listing.price = Money("0.99", "USD")
    variant_channel_listing.save()
    room_channel_listing.refresh_from_db()

    assert room_channel_listing.discounted_price == Money("10", "USD")

    update_rooms_discounted_prices_of_catalogues(room_ids=[room.pk])

    room_channel_listing.refresh_from_db()
    assert room_channel_listing.discounted_price == variant_channel_listing.price


def test_update_rooms_discounted_prices_of_catalogues_for_category(
    category, room, channel_USD
):
    variant = room.variants.first()
    variant_channel_listing = variant.channel_listings.get(
        channel=channel_USD,
        variant=variant,
    )
    variant_channel_listing.price = Money("0.89", "USD")
    variant_channel_listing.save()
    room_channel_listing = room.channel_listings.get(
        channel_id=channel_USD.id, room_id=room.id
    )
    room_channel_listing.refresh_from_db()

    assert room_channel_listing.discounted_price == Money("10", "USD")
    update_rooms_discounted_prices_of_catalogues(category_ids=[room.category_id])
    room_channel_listing.refresh_from_db()
    assert room_channel_listing.discounted_price == variant_channel_listing.price


def test_update_rooms_discounted_prices_of_catalogues_for_collection(
    collection, room, channel_USD
):
    variant = room.variants.first()
    variant_channel_listing = variant.channel_listings.get(
        channel=channel_USD,
        variant=variant,
    )
    variant_channel_listing.price = Money("0.79", "USD")
    room_channel_listing = room.channel_listings.get(channel_id=channel_USD.id)
    variant_channel_listing.save()
    room_channel_listing.refresh_from_db()
    collection.rooms.add(room)
    assert room_channel_listing.discounted_price == Money("10", "USD")

    update_rooms_discounted_prices_of_catalogues(collection_ids=[collection.pk])
    room_channel_listing.refresh_from_db()
    assert room_channel_listing.discounted_price == variant_channel_listing.price


def test_update_rooms_discounted_prices_task(room_list):

    price = Money("0.01", "USD")
    for room in room_list:
        room_channel_listing = room.channel_listings.get()
        assert room_channel_listing.discounted_price != price
        variant = room.variants.first()
        variant_channel_listing = variant.channel_listings.get()
        variant_channel_listing.price = price
        variant_channel_listing.save()
        # Check that "variant.save()" doesn't update the "discounted_price"
        assert room_channel_listing.discounted_price != price
    update_rooms_discounted_prices_task.apply(
        kwargs={"room_ids": [room.pk for room in room_list]}
    )
    for room in room_list:
        room.refresh_from_db()
        room_channel_listing = room.channel_listings.get()
        assert room_channel_listing.discounted_price == price


@patch(
    "vanphong.room.management.commands"
    ".update_all_rooms_discounted_prices"
    ".update_room_discounted_price"
)
def test_management_commmand_update_all_rooms_discounted_price(
    mock_update_room_discounted_price, room_list
):
    call_command("update_all_rooms_discounted_prices")
    call_args_list = mock_update_room_discounted_price.call_args_list
    for (args, kwargs), room in zip(call_args_list, room_list):
        assert args[0] == room
