import os
from decimal import Decimal
from unittest.mock import patch

import pytest
from freezegun import freeze_time
from prices import Money

from ...account import events as account_events
from ...attribute.utils import associate_attribute_values_to_instance
from ...graphql.room.filters import filter_rooms_by_attributes_values
from .. import models
from ..models import DigitalContentUrl
from ..thumbnails import create_room_thumbnails
from ..utils.costs import get_margin_for_variant_channel_listing
from ..utils.digital_rooms import increment_download_count


def test_filtering_by_attribute(
    db, color_attribute, size_attribute, category, channel_USD, settings
):
    room_type_a = models.RoomType.objects.create(
        name="New class", slug="new-class1", has_variants=True
    )
    room_type_a.room_attributes.add(color_attribute)
    room_type_b = models.RoomType.objects.create(
        name="New class", slug="new-class2", has_variants=True
    )
    room_type_b.variant_attributes.add(color_attribute)
    room_a = models.Room.objects.create(
        name="Test room a",
        slug="test-room-a",
        room_type=room_type_a,
        category=category,
    )
    variant_a = models.RoomVariant.objects.create(room=room_a, sku="1234")
    models.RoomVariantChannelListing.objects.create(
        variant=variant_a,
        channel=channel_USD,
        cost_price_amount=Decimal(1),
        price_amount=Decimal(10),
        currency=channel_USD.currency_code,
    )
    room_b = models.Room.objects.create(
        name="Test room b",
        slug="test-room-b",
        room_type=room_type_b,
        category=category,
    )
    variant_b = models.RoomVariant.objects.create(room=room_b, sku="12345")
    models.RoomVariantChannelListing.objects.create(
        variant=variant_b,
        channel=channel_USD,
        cost_price_amount=Decimal(1),
        price_amount=Decimal(10),
        currency=channel_USD.currency_code,
    )
    color = color_attribute.values.first()
    color_2 = color_attribute.values.last()

    # Associate color to a room and a variant
    associate_attribute_values_to_instance(room_a, color_attribute, color)
    associate_attribute_values_to_instance(variant_b, color_attribute, color)

    room_qs = models.Room.objects.all().values_list("pk", flat=True)

    filters = {color_attribute.pk: [color.pk]}
    filtered = filter_rooms_by_attributes_values(room_qs, filters)
    assert room_a.pk in list(filtered)
    assert room_b.pk in list(filtered)

    associate_attribute_values_to_instance(room_a, color_attribute, color_2)

    filters = {color_attribute.pk: [color.pk]}
    filtered = filter_rooms_by_attributes_values(room_qs, filters)

    assert room_a.pk not in list(filtered)
    assert room_b.pk in list(filtered)

    filters = {color_attribute.pk: [color_2.pk]}
    filtered = filter_rooms_by_attributes_values(room_qs, filters)
    assert room_a.pk in list(filtered)
    assert room_b.pk not in list(filtered)

    # Filter by multiple values, should trigger a OR condition
    filters = {color_attribute.pk: [color.pk, color_2.pk]}
    filtered = filter_rooms_by_attributes_values(room_qs, filters)
    assert room_a.pk in list(filtered)
    assert room_b.pk in list(filtered)

    # Associate additional attribute to a room
    size = size_attribute.values.first()
    room_type_a.room_attributes.add(size_attribute)
    associate_attribute_values_to_instance(room_a, size_attribute, size)

    # Filter by multiple attributes
    filters = {color_attribute.pk: [color_2.pk], size_attribute.pk: [size.pk]}
    filtered = filter_rooms_by_attributes_values(room_qs, filters)
    assert room_a.pk in list(filtered)


@pytest.mark.parametrize(
    "expected_price, include_discounts",
    [(Decimal("10.00"), True), (Decimal("15.0"), False)],
)
def test_get_price(
    room_type,
    category,
    sale,
    expected_price,
    include_discounts,
    site_settings,
    discount_info,
    channel_USD,
):
    room = models.Room.objects.create(
        room_type=room_type,
        category=category,
    )
    variant = room.variants.create()
    channel_listing = models.RoomVariantChannelListing.objects.create(
        variant=variant,
        channel=channel_USD,
        price_amount=Decimal(15),
        currency=channel_USD.currency_code,
    )
    discounts = [discount_info] if include_discounts else []
    price = variant.get_price(room, [], channel_USD, channel_listing, discounts)
    assert price.amount == expected_price


def test_room_get_price_do_not_charge_taxes(
    room_type, category, discount_info, channel_USD
):
    room = models.Room.objects.create(
        room_type=room_type,
        category=category,
        charge_taxes=False,
    )
    variant = room.variants.create()
    channel_listing = models.RoomVariantChannelListing.objects.create(
        variant=variant,
        channel=channel_USD,
        price_amount=Decimal(10),
        currency=channel_USD.currency_code,
    )
    price = variant.get_price(
        room, [], channel_USD, channel_listing, discounts=[discount_info]
    )
    assert price == Money("5.00", "USD")


def test_digital_room_view(client, digital_content_url):
    """Ensure a user (anonymous or not) can download a non-expired digital good
    using its associated token and that all associated events
    are correctly generated."""

    url = digital_content_url.get_absolute_url()
    response = client.get(url)
    filename = os.path.basename(digital_content_url.content.content_file.name)

    assert response.status_code == 200
    assert response["content-type"] == "image/jpeg"
    assert response["content-disposition"] == 'attachment; filename="%s"' % filename

    # Ensure an event was generated from downloading a digital good.
    # The validity of this event is checked in test_digital_room_increment_download
    assert account_events.CustomerEvent.objects.exists()


@pytest.mark.parametrize(
    "is_user_null, is_line_null", ((False, False), (False, True), (True, True))
)
def test_digital_room_increment_download(
    client,
    customer_user,
    digital_content_url: DigitalContentUrl,
    is_user_null,
    is_line_null,
):
    """Ensure downloading a digital good is possible without it
    being associated to an order line/user."""

    expected_user = customer_user

    if is_line_null:
        expected_user = None
        digital_content_url.line = None
        digital_content_url.save(update_fields=["line"])
    elif is_user_null:
        expected_user = None
        digital_content_url.line.user = None
        digital_content_url.line.save(update_fields=["user"])

    expected_new_download_count = digital_content_url.download_num + 1
    increment_download_count(digital_content_url)
    assert digital_content_url.download_num == expected_new_download_count

    if expected_user is None:
        # Ensure an event was not generated from downloading a digital good
        # as no user could be found
        assert not account_events.CustomerEvent.objects.exists()
        return

    download_event = account_events.CustomerEvent.objects.get()
    assert download_event.type == account_events.CustomerEvents.DIGITAL_LINK_DOWNLOADED
    assert download_event.user == expected_user
    assert download_event.order == digital_content_url.line.order
    assert download_event.parameters == {"order_line_pk": digital_content_url.line.pk}


def test_digital_room_view_url_downloaded_max_times(client, digital_content):
    digital_content.use_default_settings = False
    digital_content.max_downloads = 1
    digital_content.save()
    digital_content_url = DigitalContentUrl.objects.create(content=digital_content)

    url = digital_content_url.get_absolute_url()
    response = client.get(url)

    # first download
    assert response.status_code == 200

    # second download
    response = client.get(url)
    assert response.status_code == 404


def test_digital_room_view_url_expired(client, digital_content):
    digital_content.use_default_settings = False
    digital_content.url_valid_days = 10
    digital_content.save()

    with freeze_time("2018-05-31 12:00:01"):
        digital_content_url = DigitalContentUrl.objects.create(content=digital_content)

    url = digital_content_url.get_absolute_url()
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.parametrize(
    "price, cost", [(Money("0", "USD"), Money("1", "USD")), (Money("2", "USD"), None)]
)
def test_costs_get_margin_for_variant_channel_listing(
    variant, price, cost, channel_USD
):
    variant_channel_listing = variant.channel_listings.filter(
        channel_id=channel_USD.id
    ).first()
    variant_channel_listing.cost_price = cost
    variant_channel_listing.price = price
    assert not get_margin_for_variant_channel_listing(variant_channel_listing)


@patch("vanphong.room.thumbnails.create_thumbnails")
def test_create_room_thumbnails(mock_create_thumbnails, room_with_image):
    room_image = room_with_image.images.first()
    create_room_thumbnails(room_image.pk)
    assert mock_create_thumbnails.call_count == 1
    args, kwargs = mock_create_thumbnails.call_args
    assert kwargs == {
        "model": models.RoomImage,
        "pk": room_image.pk,
        "size_set": "rooms",
    }
