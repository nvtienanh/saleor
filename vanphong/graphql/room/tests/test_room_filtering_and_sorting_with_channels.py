import datetime
import uuid
from decimal import Decimal

import pytest

from ....room.models import (
    Room,
    RoomChannelListing,
    RoomType,
    RoomVariant,
    RoomVariantChannelListing,
)
from ...channel.filters import LACK_OF_CHANNEL_IN_FILTERING_MSG
from ...channel.sorters import LACK_OF_CHANNEL_IN_SORTING_MSG
from ...tests.utils import assert_graphql_error_with_message, get_graphql_content


@pytest.fixture
def rooms_for_sorting_with_channels(category, channel_USD, channel_PLN):
    room_type = RoomType.objects.create(name="Apple")
    rooms = Room.objects.bulk_create(
        [
            Room(
                name="Room1",
                slug="prod1",
                category=category,
                room_type=room_type,
                description="desc1",
            ),
            Room(
                name="RoomRoom1",
                slug="prod_prod1",
                category=category,
                room_type=room_type,
            ),
            Room(
                name="RoomRoom2",
                slug="prod_prod2",
                category=category,
                room_type=room_type,
            ),
            Room(
                name="Room2",
                slug="prod2",
                category=category,
                room_type=room_type,
                description="desc2",
            ),
            Room(
                name="Room3",
                slug="prod3",
                category=category,
                room_type=room_type,
                description="desc3",
            ),
        ]
    )
    RoomChannelListing.objects.bulk_create(
        [
            RoomChannelListing(
                room=rooms[0],
                channel=channel_USD,
                is_published=True,
                discounted_price_amount=Decimal(5),
                publication_date=datetime.date(2002, 1, 1),
            ),
            RoomChannelListing(
                room=rooms[1],
                channel=channel_USD,
                is_published=True,
                discounted_price_amount=Decimal(15),
                publication_date=datetime.date(2000, 1, 1),
            ),
            RoomChannelListing(
                room=rooms[2],
                channel=channel_USD,
                is_published=False,
                discounted_price_amount=Decimal(4),
                publication_date=datetime.date(1999, 1, 1),
            ),
            RoomChannelListing(
                room=rooms[3],
                channel=channel_USD,
                is_published=True,
                discounted_price_amount=Decimal(7),
                publication_date=datetime.date(2001, 1, 1),
            ),
            # Second channel
            RoomChannelListing(
                room=rooms[0],
                channel=channel_PLN,
                is_published=False,
                discounted_price_amount=Decimal(15),
                publication_date=datetime.date(2003, 1, 1),
            ),
            RoomChannelListing(
                room=rooms[1],
                channel=channel_PLN,
                is_published=True,
                discounted_price_amount=Decimal(4),
                publication_date=datetime.date(1999, 1, 1),
            ),
            RoomChannelListing(
                room=rooms[2],
                channel=channel_PLN,
                is_published=True,
                discounted_price_amount=Decimal(5),
                publication_date=datetime.date(2000, 1, 1),
            ),
            RoomChannelListing(
                room=rooms[4],
                channel=channel_PLN,
                is_published=True,
                discounted_price_amount=Decimal(7),
                publication_date=datetime.date(1998, 1, 1),
            ),
        ]
    )
    variants = RoomVariant.objects.bulk_create(
        [
            RoomVariant(
                room=rooms[0],
                sku=str(uuid.uuid4()).replace("-", ""),
                track_inventory=True,
            ),
            RoomVariant(
                room=rooms[1],
                sku=str(uuid.uuid4()).replace("-", ""),
                track_inventory=True,
            ),
            RoomVariant(
                room=rooms[2],
                sku=str(uuid.uuid4()).replace("-", ""),
                track_inventory=True,
            ),
            RoomVariant(
                room=rooms[3],
                sku=str(uuid.uuid4()).replace("-", ""),
                track_inventory=True,
            ),
            RoomVariant(
                room=rooms[4],
                sku=str(uuid.uuid4()).replace("-", ""),
                track_inventory=True,
            ),
        ]
    )
    RoomVariantChannelListing.objects.bulk_create(
        [
            RoomVariantChannelListing(
                variant=variants[0],
                channel=channel_USD,
                price_amount=Decimal(10),
                currency=channel_USD.currency_code,
            ),
            RoomVariantChannelListing(
                variant=variants[1],
                channel=channel_USD,
                price_amount=Decimal(15),
                currency=channel_USD.currency_code,
            ),
            RoomVariantChannelListing(
                variant=variants[2],
                channel=channel_USD,
                price_amount=Decimal(8),
                currency=channel_USD.currency_code,
            ),
            RoomVariantChannelListing(
                variant=variants[3],
                channel=channel_USD,
                price_amount=Decimal(7),
                currency=channel_USD.currency_code,
            ),
            # Second channel
            RoomVariantChannelListing(
                variant=variants[0],
                channel=channel_PLN,
                price_amount=Decimal(15),
                currency=channel_PLN.currency_code,
            ),
            RoomVariantChannelListing(
                variant=variants[1],
                channel=channel_PLN,
                price_amount=Decimal(8),
                currency=channel_PLN.currency_code,
            ),
            RoomVariantChannelListing(
                variant=variants[2],
                channel=channel_PLN,
                price_amount=Decimal(10),
                currency=channel_PLN.currency_code,
            ),
            RoomVariantChannelListing(
                variant=variants[4],
                channel=channel_PLN,
                price_amount=Decimal(7),
                currency=channel_PLN.currency_code,
            ),
        ]
    )
    return rooms


QUERY_ROOMS_WITH_SORTING_AND_FILTERING = """
    query ($sortBy: RoomOrder, $filter: RoomFilterInput){
        rooms (
            first: 10, sortBy: $sortBy, filter: $filter
        ) {
            edges {
                node {
                    name
                    slug
                }
            }
        }
    }
"""


@pytest.mark.parametrize(
    "sort_by",
    [
        {"field": "PUBLISHED", "direction": "ASC"},
        {"field": "PRICE", "direction": "DESC"},
        {"field": "MINIMAL_PRICE", "direction": "DESC"},
        {"field": "PUBLICATION_DATE", "direction": "DESC"},
    ],
)
def test_rooms_with_sorting_and_without_channel(
    sort_by,
    staff_api_client,
    permission_manage_rooms,
):
    # given
    variables = {"sortBy": sort_by}

    # when
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_WITH_SORTING_AND_FILTERING,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    assert_graphql_error_with_message(response, LACK_OF_CHANNEL_IN_SORTING_MSG)


@pytest.mark.parametrize(
    "sort_by, rooms_order",
    [
        (
            {"field": "PUBLISHED", "direction": "ASC"},
            ["RoomRoom2", "Room1", "Room2", "RoomRoom1", "Room3"],
        ),
        (
            {"field": "PUBLISHED", "direction": "DESC"},
            ["Room3", "RoomRoom1", "Room2", "Room1", "RoomRoom2"],
        ),
        (
            {"field": "PRICE", "direction": "ASC"},
            ["Room2", "RoomRoom2", "Room1", "RoomRoom1", "Room3"],
        ),
        (
            {"field": "PRICE", "direction": "DESC"},
            ["Room3", "RoomRoom1", "Room1", "RoomRoom2", "Room2"],
        ),
        (
            {"field": "MINIMAL_PRICE", "direction": "ASC"},
            ["RoomRoom2", "Room1", "Room2", "RoomRoom1", "Room3"],
        ),
        (
            {"field": "MINIMAL_PRICE", "direction": "DESC"},
            ["Room3", "RoomRoom1", "Room2", "Room1", "RoomRoom2"],
        ),
        (
            {"field": "PUBLICATION_DATE", "direction": "ASC"},
            ["RoomRoom2", "RoomRoom1", "Room2", "Room1", "Room3"],
        ),
        (
            {"field": "PUBLICATION_DATE", "direction": "DESC"},
            ["Room3", "Room1", "Room2", "RoomRoom1", "RoomRoom2"],
        ),
    ],
)
def test_rooms_with_sorting_and_channel_USD(
    sort_by,
    rooms_order,
    staff_api_client,
    permission_manage_rooms,
    rooms_for_sorting_with_channels,
    channel_USD,
):
    # given
    sort_by["channel"] = channel_USD.slug
    variables = {"sortBy": sort_by}

    # when
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_WITH_SORTING_AND_FILTERING,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    for index, room_name in enumerate(rooms_order):
        assert room_name == rooms_nodes[index]["node"]["name"]


@pytest.mark.parametrize(
    "sort_by, rooms_order",
    [
        (
            {"field": "PUBLISHED", "direction": "ASC"},
            ["Room1", "Room3", "RoomRoom1", "RoomRoom2", "Room2"],
        ),
        (
            {"field": "PUBLISHED", "direction": "DESC"},
            ["Room2", "RoomRoom2", "RoomRoom1", "Room3", "Room1"],
        ),
        (
            {"field": "PRICE", "direction": "ASC"},
            ["Room3", "RoomRoom1", "RoomRoom2", "Room1", "Room2"],
        ),
        (
            {"field": "PRICE", "direction": "DESC"},
            ["Room2", "Room1", "RoomRoom2", "RoomRoom1", "Room3"],
        ),
        (
            {"field": "MINIMAL_PRICE", "direction": "ASC"},
            ["RoomRoom1", "RoomRoom2", "Room3", "Room1", "Room2"],
        ),
        (
            {"field": "MINIMAL_PRICE", "direction": "DESC"},
            ["Room2", "Room1", "Room3", "RoomRoom2", "RoomRoom1"],
        ),
    ],
)
def test_rooms_with_sorting_and_channel_PLN(
    sort_by,
    rooms_order,
    staff_api_client,
    permission_manage_rooms,
    rooms_for_sorting_with_channels,
    channel_PLN,
):
    # given
    sort_by["channel"] = channel_PLN.slug
    variables = {"sortBy": sort_by}

    # when
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_WITH_SORTING_AND_FILTERING,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    for index, room_name in enumerate(rooms_order):
        assert room_name == rooms_nodes[index]["node"]["name"]


@pytest.mark.parametrize(
    "sort_by",
    [
        {"field": "PUBLISHED", "direction": "ASC"},
        {"field": "PRICE", "direction": "ASC"},
        {"field": "MINIMAL_PRICE", "direction": "ASC"},
    ],
)
def test_rooms_with_sorting_and_not_existing_channel_asc(
    sort_by,
    staff_api_client,
    permission_manage_rooms,
    rooms_for_sorting_with_channels,
    channel_USD,
):
    # given
    rooms_order = [
        "Room1",
        "Room2",
        "Room3",
        "RoomRoom1",
        "RoomRoom2",
    ]
    sort_by["channel"] = "Not-existing"
    variables = {"sortBy": sort_by}

    # when
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_WITH_SORTING_AND_FILTERING,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    for index, room_name in enumerate(rooms_order):
        assert room_name == rooms_nodes[index]["node"]["name"]


@pytest.mark.parametrize(
    "sort_by",
    [
        {"field": "PUBLISHED", "direction": "DESC"},
        {"field": "PRICE", "direction": "DESC"},
        {"field": "MINIMAL_PRICE", "direction": "DESC"},
    ],
)
def test_rooms_with_sorting_and_not_existing_channel_desc(
    sort_by,
    staff_api_client,
    permission_manage_rooms,
    rooms_for_sorting_with_channels,
    channel_USD,
):
    rooms_order = [
        "RoomRoom2",
        "RoomRoom1",
        "Room3",
        "Room2",
        "Room1",
    ]
    # given
    sort_by["channel"] = "Not-existing"
    variables = {"sortBy": sort_by}

    # when
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_WITH_SORTING_AND_FILTERING,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    for index, room_name in enumerate(rooms_order):
        assert room_name == rooms_nodes[index]["node"]["name"]


@pytest.mark.parametrize(
    "filter_by",
    [{"isPublished": True}, {"price": {"lte": 5}}, {"minimalPrice": {"lte": 5}}],
)
def test_rooms_with_filtering_without_channel(
    filter_by, staff_api_client, permission_manage_rooms
):
    # given
    variables = {"filter": filter_by}

    # when
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_WITH_SORTING_AND_FILTERING,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    assert_graphql_error_with_message(response, LACK_OF_CHANNEL_IN_FILTERING_MSG)


@pytest.mark.parametrize(
    "filter_by, rooms_count",
    [
        ({"isPublished": True}, 3),
        ({"isPublished": False}, 1),
        ({"price": {"lte": 8}}, 2),
        ({"price": {"gte": 11}}, 1),
        ({"minimalPrice": {"lte": 4}}, 1),
        ({"minimalPrice": {"gte": 5}}, 3),
    ],
)
def test_rooms_with_filtering_with_channel_USD(
    filter_by,
    rooms_count,
    staff_api_client,
    permission_manage_rooms,
    rooms_for_sorting_with_channels,
    channel_USD,
):
    # given
    filter_by["channel"] = channel_USD.slug
    variables = {"filter": filter_by}

    # when
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_WITH_SORTING_AND_FILTERING,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    assert len(rooms_nodes) == rooms_count


@pytest.mark.parametrize(
    "filter_by, rooms_count",
    [
        ({"isPublished": True}, 3),
        ({"isPublished": False}, 1),
        ({"price": {"lte": 8}}, 2),
        ({"price": {"gte": 11}}, 1),
        ({"minimalPrice": {"lte": 4}}, 1),
        ({"minimalPrice": {"gte": 5}}, 3),
    ],
)
def test_rooms_with_filtering_with_channel_PLN(
    filter_by,
    rooms_count,
    staff_api_client,
    permission_manage_rooms,
    rooms_for_sorting_with_channels,
    channel_PLN,
):
    # given
    filter_by["channel"] = channel_PLN.slug
    variables = {"filter": filter_by}

    # when
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_WITH_SORTING_AND_FILTERING,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    assert len(rooms_nodes) == rooms_count


@pytest.mark.parametrize(
    "filter_by",
    [
        {"isPublished": True},
        {"isPublished": False},
        {"price": {"lte": 8}},
        {"price": {"gte": 11}},
        {"minimalPrice": {"lte": 4}},
        {"minimalPrice": {"gte": 5}},
    ],
)
def test_rooms_with_filtering_and_not_existing_channel(
    filter_by,
    staff_api_client,
    permission_manage_rooms,
    rooms_for_sorting_with_channels,
    channel_USD,
):
    # given
    filter_by["channel"] = "Not-existing"
    variables = {"filter": filter_by}

    # when
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_WITH_SORTING_AND_FILTERING,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    assert len(rooms_nodes) == 0
