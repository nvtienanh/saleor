from .....attribute.models import Attribute
from .....channel.models import Channel
from .....graphql.csv.enums import RoomFieldEnum
from ....utils.room_headers import (
    get_attributes_headers,
    get_channels_headers,
    get_export_fields_and_headers_info,
    get_room_export_fields_and_headers,
    get_hotels_headers,
)


def test_get_export_fields_and_headers_fields_without_price():
    # given
    export_info = {
        "fields": [
            RoomFieldEnum.COLLECTIONS.value,
            RoomFieldEnum.DESCRIPTION.value,
            RoomFieldEnum.VARIANT_SKU.value,
        ],
        "warehoses": [],
    }

    # when
    export_fields, file_headers = get_room_export_fields_and_headers(export_info)

    # then
    expected_headers = ["id", "collections", "description", "variant sku"]

    assert set(export_fields) == {
        "collections__slug",
        "id",
        "variants__sku",
        "description",
    }
    assert file_headers == expected_headers


def test_get_export_fields_and_headers_no_fields():
    export_fields, file_headers = get_room_export_fields_and_headers({})

    assert export_fields == ["id"]
    assert file_headers == ["id"]


def test_get_attributes_headers(room_with_multiple_values_attributes):
    # given
    attribute_ids = Attribute.objects.values_list("id", flat=True)
    export_info = {"attributes": attribute_ids}

    # when
    attributes_headers = get_attributes_headers(export_info)

    # then
    room_headers = []
    variant_headers = []
    for attr in Attribute.objects.all():
        if attr.room_types.exists():
            room_headers.append(f"{attr.slug} (room attribute)")
        if attr.room_variant_types.exists():
            variant_headers.append(f"{attr.slug} (variant attribute)")

    expected_headers = room_headers + variant_headers
    assert attributes_headers == expected_headers


def test_get_attributes_headers_lack_of_attributes_ids():
    # given
    export_info = {}

    # when
    attributes_headers = get_attributes_headers(export_info)

    # then
    assert attributes_headers == []


def test_get_hotels_headers(hotels):
    # given
    hotel_ids = [hotels[0].pk]
    export_info = {"hotels": hotel_ids}

    # when
    hotel_headers = get_hotels_headers(export_info)

    # then
    assert hotel_headers == [f"{hotels[0].slug} (hotel quantity)"]


def test_get_hotels_headers_lack_of_hotel_ids():
    # given
    export_info = {}

    # when
    hotel_headers = get_hotels_headers(export_info)

    # then
    assert hotel_headers == []


def test_get_channels_headers(channel_USD, channel_PLN):
    # given
    channel_usd_slug = channel_USD.slug
    channel_pln_slug = channel_PLN.slug

    channel_ids = [channel_USD.pk, channel_PLN.pk]
    export_info = {"channels": channel_ids}

    # when
    channel_headers = get_channels_headers(export_info)

    # then
    expected_headers = []
    for channel_slug in [channel_pln_slug, channel_usd_slug]:
        for field in [
            "room currency code",
            "published",
            "publication date",
            "searchable",
            "available for purchase",
            "price amount",
            "variant currency code",
            "variant cost price",
        ]:
            expected_headers.append(f"{channel_slug} (channel {field})")
    assert channel_headers == expected_headers


def test_get_channels_headers_lack_of_channel_ids():
    # given
    export_info = {}

    # when
    channel_headers = get_channels_headers(export_info)

    # then
    assert channel_headers == []


def test_get_export_fields_and_headers_info(
    hotels, room_with_multiple_values_attributes, channel_PLN, channel_USD
):
    # given
    hotel_ids = [w.pk for w in hotels]
    attribute_ids = [attr.pk for attr in Attribute.objects.all()]
    channel_ids = [channel_PLN.pk, channel_USD.pk]
    export_info = {
        "fields": [
            RoomFieldEnum.COLLECTIONS.value,
            RoomFieldEnum.DESCRIPTION.value,
        ],
        "hotels": hotel_ids,
        "attributes": attribute_ids,
        "channels": channel_ids,
    }

    expected_file_headers = [
        "id",
        "collections",
        "description",
    ]

    # when
    export_fields, file_headers, data_headers = get_export_fields_and_headers_info(
        export_info
    )

    # then
    expected_fields = [
        "id",
        "collections__slug",
        "description",
    ]

    room_headers = []
    variant_headers = []
    for attr in Attribute.objects.all().order_by("slug"):
        if attr.room_types.exists():
            room_headers.append(f"{attr.slug} (room attribute)")
        if attr.room_variant_types.exists():
            variant_headers.append(f"{attr.slug} (variant attribute)")

    hotel_headers = [f"{w.slug} (hotel quantity)" for w in hotels]

    channel_headers = []
    for channel in Channel.objects.all().order_by("slug"):
        slug = channel.slug
        for field in [
            "room currency code",
            "published",
            "publication date",
            "searchable",
            "available for purchase",
            "price amount",
            "variant currency code",
            "variant cost price",
        ]:
            channel_headers.append(f"{slug} (channel {field})")

    excepted_headers = (
        expected_fields
        + room_headers
        + variant_headers
        + hotel_headers
        + channel_headers
    )

    expected_file_headers += (
        room_headers + variant_headers + hotel_headers + channel_headers
    )
    assert expected_file_headers == file_headers
    assert set(export_fields) == set(expected_fields)
    assert data_headers == excepted_headers
