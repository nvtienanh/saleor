import datetime
from decimal import Decimal
from unittest.mock import Mock

from freezegun import freeze_time
from prices import Money, TaxedMoney, TaxedMoneyRange

from ...plugins.manager import PluginsManager
from .. import models
from ..utils.availability import get_room_availability


def test_availability(stock, monkeypatch, settings, channel_USD):
    room = stock.room_variant.room
    room_channel_listing = room.channel_listings.first()
    variants = room.variants.all()
    variants_channel_listing = models.RoomVariantChannelListing.objects.filter(
        variant__in=variants
    )
    taxed_price = TaxedMoney(Money("10.0", "USD"), Money("12.30", "USD"))
    monkeypatch.setattr(
        PluginsManager, "apply_taxes_to_room", Mock(return_value=taxed_price)
    )
    availability = get_room_availability(
        room=room,
        room_channel_listing=room_channel_listing,
        variants=room.variants.all(),
        variants_channel_listing=variants_channel_listing,
        channel=channel_USD,
        collections=[],
        discounts=[],
        country="PL",
    )
    taxed_price_range = TaxedMoneyRange(start=taxed_price, stop=taxed_price)
    assert availability.price_range == taxed_price_range
    assert availability.price_range_local_currency is None

    monkeypatch.setattr(
        "django_prices_openexchangerates.models.get_rates",
        lambda c: {"PLN": Mock(rate=2)},
    )
    settings.DEFAULT_COUNTRY = "PL"
    settings.OPENEXCHANGERATES_API_KEY = "fake-key"
    availability = get_room_availability(
        room=room,
        room_channel_listing=room_channel_listing,
        variants=variants,
        variants_channel_listing=variants_channel_listing,
        collections=[],
        discounts=[],
        channel=channel_USD,
        local_currency="PLN",
        country="PL",
    )
    assert availability.price_range_local_currency.start.currency == "PLN"

    availability = get_room_availability(
        room=room,
        room_channel_listing=room_channel_listing,
        variants=variants,
        variants_channel_listing=variants_channel_listing,
        collections=[],
        discounts=[],
        channel=channel_USD,
        country="PL",
    )
    assert availability.price_range.start.tax.amount
    assert availability.price_range.stop.tax.amount
    assert availability.price_range_undiscounted.start.tax.amount
    assert availability.price_range_undiscounted.stop.tax.amount


def test_availability_with_all_variant_channel_listings(stock, channel_USD):
    # given
    room = stock.room_variant.room
    room_channel_listing = room.channel_listings.first()
    variants = room.variants.all()
    variants_channel_listing = models.RoomVariantChannelListing.objects.filter(
        variant__in=variants, channel=channel_USD
    )
    [variant1_channel_listing, variant2_channel_listing] = variants_channel_listing
    variant2_channel_listing.price_amount = Decimal(15)
    variant2_channel_listing.save()

    # when
    availability = get_room_availability(
        room=room,
        room_channel_listing=room_channel_listing,
        variants=variants,
        variants_channel_listing=variants_channel_listing,
        channel=channel_USD,
        collections=[],
        discounts=[],
        country="PL",
    )

    # then
    price_range = availability.price_range
    assert price_range.start.gross.amount == variant1_channel_listing.price_amount
    assert price_range.stop.gross.amount == variant2_channel_listing.price_amount


def test_availability_with_missing_variant_channel_listings(stock, channel_USD):
    # given
    room = stock.room_variant.room
    room_channel_listing = room.channel_listings.first()
    variants = room.variants.all()
    variants_channel_listing = models.RoomVariantChannelListing.objects.filter(
        variant__in=variants, channel=channel_USD
    )
    [variant1_channel_listing, variant2_channel_listing] = variants_channel_listing
    variant2_channel_listing.delete()

    # when
    availability = get_room_availability(
        room=room,
        room_channel_listing=room_channel_listing,
        variants=variants,
        variants_channel_listing=variants_channel_listing,
        channel=channel_USD,
        collections=[],
        discounts=[],
        country="PL",
    )

    # then
    price_range = availability.price_range
    assert price_range.start.gross.amount == variant1_channel_listing.price_amount
    assert price_range.stop.gross.amount == variant1_channel_listing.price_amount


def test_availability_without_variant_channel_listings(stock, channel_USD):
    # given
    room = stock.room_variant.room
    room_channel_listing = room.channel_listings.first()
    variants = room.variants.all()
    models.RoomVariantChannelListing.objects.filter(
        variant__in=variants, channel=channel_USD
    ).delete()

    # when
    availability = get_room_availability(
        room=room,
        room_channel_listing=room_channel_listing,
        variants=variants,
        variants_channel_listing=[],
        channel=channel_USD,
        collections=[],
        discounts=[],
        country="PL",
    )

    # then
    price_range = availability.price_range
    assert price_range is None


def test_available_rooms_only_published(room_list, channel_USD):
    channel_listing = room_list[0].channel_listings.get()
    channel_listing.is_published = False
    channel_listing.save(update_fields=["is_published"])

    available_rooms = models.Room.objects.published(channel_USD.slug)
    assert available_rooms.count() == 2
    assert all(
        [
            room.channel_listings.get(channel__slug=channel_USD.slug).is_published
            for room in available_rooms
        ]
    )


def test_available_rooms_only_available(room_list, channel_USD):
    channel_listing = room_list[0].channel_listings.get()
    date_tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    channel_listing.publication_date = date_tomorrow
    channel_listing.save(update_fields=["publication_date"])

    available_rooms = models.Room.objects.published(channel_USD.slug)
    assert available_rooms.count() == 2
    assert all(
        [
            room.channel_listings.get(channel__slug=channel_USD.slug).is_published
            for room in available_rooms
        ]
    )


def test_available_rooms_available_from_yesterday(room_list, channel_USD):
    channel_listing = room_list[0].channel_listings.get()
    date_tomorrow = datetime.date.today() - datetime.timedelta(days=1)
    channel_listing.publication_date = date_tomorrow
    channel_listing.save(update_fields=["publication_date"])

    available_rooms = models.Room.objects.published(channel_USD.slug)
    assert available_rooms.count() == 3
    assert all(
        [
            room.channel_listings.get(channel__slug=channel_USD.slug).is_published
            for room in available_rooms
        ]
    )


def test_available_rooms_available_without_channel_listings(
    room_list, channel_PLN
):
    available_rooms = models.Room.objects.published(channel_PLN.slug)
    assert available_rooms.count() == 0


def test_available_rooms_available_with_many_channels(
    room_list_with_many_channels, channel_USD, channel_PLN
):
    models.RoomChannelListing.objects.filter(
        room__in=room_list_with_many_channels, channel=channel_PLN
    ).update(is_published=False)

    available_rooms = models.Room.objects.published(channel_PLN.slug)
    assert available_rooms.count() == 0
    available_rooms = models.Room.objects.published(channel_USD.slug)
    assert available_rooms.count() == 3


@freeze_time("2020-03-18 12:00:00")
def test_room_is_visible_from_today(room):
    room_channel_listing = room.channel_listings.get()
    room_channel_listing.publication_date = datetime.date.today()
    room_channel_listing.save()
    assert room_channel_listing.is_visible


def test_available_rooms_with_variants(room_list, channel_USD):
    room = room_list[0]
    room.variants.all().delete()

    available_rooms = models.Room.objects.published_with_variants(
        channel_USD.slug
    )
    assert available_rooms.count() == 2


def test_available_rooms_with_variants_in_many_channels_usd(
    room_list_with_variants_many_channel, channel_USD
):
    available_rooms = models.Room.objects.published_with_variants(
        channel_USD.slug
    )
    assert available_rooms.count() == 1


def test_available_rooms_with_variants_in_many_channels_pln(
    room_list_with_variants_many_channel, channel_PLN
):
    available_rooms = models.Room.objects.published_with_variants(
        channel_PLN.slug
    )
    assert available_rooms.count() == 2


def test_visible_to_customer_user(customer_user, room_list, channel_USD):
    room = room_list[0]
    room.variants.all().delete()

    available_rooms = models.Room.objects.visible_to_user(
        customer_user, channel_USD.slug
    )
    assert available_rooms.count() == 2


def test_visible_to_staff_user(
    staff_user, room_list, channel_USD, permission_manage_rooms
):
    room = room_list[0]
    room.variants.all().delete()

    available_rooms = models.Room.objects.visible_to_user(
        staff_user, channel_USD.slug
    )
    assert available_rooms.count() == 3


def test_filter_not_published_room_is_unpublished(room, channel_USD):
    channel_listing = room.channel_listings.get()
    channel_listing.is_published = False
    channel_listing.save(update_fields=["is_published"])

    available_rooms = models.Room.objects.not_published(channel_USD.slug)
    assert available_rooms.count() == 1


def test_filter_not_published_room_published_tomorrow(room, channel_USD):
    date_tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    channel_listing = room.channel_listings.get()
    channel_listing.is_published = True
    channel_listing.publication_date = date_tomorrow
    channel_listing.save(update_fields=["is_published", "publication_date"])

    available_rooms = models.Room.objects.not_published(channel_USD.slug)
    assert available_rooms.count() == 1


def test_filter_not_published_room_not_published_tomorrow(room, channel_USD):
    date_tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    channel_listing = room.channel_listings.get()
    channel_listing.is_published = False
    channel_listing.publication_date = date_tomorrow
    channel_listing.save(update_fields=["is_published", "publication_date"])

    available_rooms = models.Room.objects.not_published(channel_USD.slug)
    assert available_rooms.count() == 1


def test_filter_not_published_room_is_published(room, channel_USD):
    available_rooms = models.Room.objects.not_published(channel_USD.slug)
    assert available_rooms.count() == 0


def test_filter_not_published_room_is_unpublished_other_channel(
    room, channel_USD, channel_PLN
):
    models.RoomChannelListing.objects.create(
        room=room, channel=channel_PLN, is_published=False
    )

    available_rooms_usd = models.Room.objects.not_published(channel_USD.slug)
    assert available_rooms_usd.count() == 0

    available_rooms_pln = models.Room.objects.not_published(channel_PLN.slug)
    assert available_rooms_pln.count() == 1


def test_filter_not_published_room_without_assigned_channel(
    room, channel_USD, channel_PLN
):
    not_available_rooms_usd = models.Room.objects.not_published(channel_USD.slug)
    assert not_available_rooms_usd.count() == 0

    not_available_rooms_pln = models.Room.objects.not_published(channel_PLN.slug)
    assert not_available_rooms_pln.count() == 1
