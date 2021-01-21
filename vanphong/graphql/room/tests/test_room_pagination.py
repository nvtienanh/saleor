import uuid
from decimal import Decimal

import graphene
import pytest

from ....attribute.utils import associate_attribute_values_to_instance
from ....room.models import (
    Category,
    Collection,
    CollectionChannelListing,
    Room,
    RoomChannelListing,
    RoomType,
    RoomVariant,
    RoomVariantChannelListing,
)
from ....hotel.models import Stock
from ...tests.utils import get_graphql_content


@pytest.fixture
def categories_for_pagination(room_type):
    categories = Category.tree.build_tree_nodes(
        {
            "id": 1,
            "name": "Category2",
            "slug": "cat1",
            "children": [
                {"parent_id": 1, "name": "CategoryCategory1", "slug": "cat_cat1"},
                {"parent_id": 1, "name": "CategoryCategory2", "slug": "cat_cat2"},
                {"parent_id": 1, "name": "Category1", "slug": "cat2"},
                {"parent_id": 1, "name": "Category3", "slug": "cat3"},
            ],
        }
    )
    categories = Category.objects.bulk_create(categories)
    Room.objects.bulk_create(
        [
            Room(
                name="Prod1",
                slug="prod1",
                room_type=room_type,
                category=categories[4],
            ),
            Room(
                name="Prod2",
                slug="prod2",
                room_type=room_type,
                category=categories[4],
            ),
            Room(
                name="Prod3",
                slug="prod3",
                room_type=room_type,
                category=categories[2],
            ),
        ]
    )
    return categories


QUERY_CATEGORIES_PAGINATION = """
    query (
        $first: Int, $last: Int, $after: String, $before: String,
        $sortBy: CategorySortingInput, $filter: CategoryFilterInput
    ){
        categories(
            first: $first, last: $last, after: $after, before: $before,
            sortBy: $sortBy, filter: $filter
        ) {
            edges {
                node {
                    name


                }
            }
            pageInfo{
                startCursor
                endCursor
                hasNextPage
                hasPreviousPage
            }
        }
    }
"""


@pytest.mark.parametrize(
    "sort_by, categories_order",
    [
        (
            {"field": "NAME", "direction": "ASC"},
            ["Category1", "Category2", "Category3"],
        ),
        (
            {"field": "NAME", "direction": "DESC"},
            ["CategoryCategory2", "CategoryCategory1", "Category3"],
        ),
        (
            {"field": "SUBCATEGORY_COUNT", "direction": "ASC"},
            ["Category1", "Category3", "CategoryCategory1"],
        ),
        (
            {"field": "ROOM_COUNT", "direction": "ASC"},
            ["Category1", "CategoryCategory1", "CategoryCategory2"],
        ),
    ],
)
def test_categories_pagination_with_sorting(
    sort_by,
    categories_order,
    staff_api_client,
    categories_for_pagination,
):
    page_size = 3

    variables = {"first": page_size, "after": None, "sortBy": sort_by}
    response = staff_api_client.post_graphql(
        QUERY_CATEGORIES_PAGINATION,
        variables,
    )
    content = get_graphql_content(response)
    categories_nodes = content["data"]["categories"]["edges"]
    assert categories_order[0] == categories_nodes[0]["node"]["name"]
    assert categories_order[1] == categories_nodes[1]["node"]["name"]
    assert categories_order[2] == categories_nodes[2]["node"]["name"]
    assert len(categories_nodes) == page_size


@pytest.mark.parametrize(
    "filter_by, categories_order",
    [
        ({"search": "CategoryCategory"}, ["CategoryCategory1", "CategoryCategory2"]),
        ({"search": "cat_cat"}, ["CategoryCategory1", "CategoryCategory2"]),
        ({"search": "Category1"}, ["CategoryCategory1", "Category1"]),
    ],
)
def test_categories_pagination_with_filtering(
    filter_by,
    categories_order,
    staff_api_client,
    categories_for_pagination,
):
    page_size = 2

    variables = {"first": page_size, "after": None, "filter": filter_by}
    response = staff_api_client.post_graphql(
        QUERY_CATEGORIES_PAGINATION,
        variables,
    )
    content = get_graphql_content(response)
    categories_nodes = content["data"]["categories"]["edges"]
    assert categories_order[0] == categories_nodes[0]["node"]["name"]
    assert categories_order[1] == categories_nodes[1]["node"]["name"]
    assert len(categories_nodes) == page_size


@pytest.fixture
def collections_for_pagination(room, room_with_single_variant, channel_USD):
    collections = Collection.objects.bulk_create(
        [
            Collection(name="Collection1", slug="col1"),
            Collection(name="CollectionCollection1", slug="col_col1"),
            Collection(name="CollectionCollection2", slug="col_col2"),
            Collection(name="Collection2", slug="col2"),
            Collection(name="Collection3", slug="col3"),
        ]
    )
    collections[2].rooms.add(room)
    collections[4].rooms.add(room_with_single_variant)
    published = (True, True, False, False, True)
    CollectionChannelListing.objects.bulk_create(
        [
            CollectionChannelListing(
                channel=channel_USD, is_published=published[num], collection=collection
            )
            for num, collection in enumerate(collections)
        ]
    )
    return collections


QUERY_COLLECTIONS_PAGINATION = """
    query (
        $first: Int, $last: Int, $after: String, $before: String,
        $sortBy: CollectionSortingInput, $filter: CollectionFilterInput
    ){
        collections (
            first: $first, last: $last, after: $after, before: $before,
            sortBy: $sortBy, filter: $filter
        ) {
            edges {
                node {
                    name
                    rooms{
                        totalCount
                    }
                }
            }
            pageInfo{
                startCursor
                endCursor
                hasNextPage
                hasPreviousPage
            }
        }
    }
"""


@pytest.mark.parametrize(
    "sort_by, collections_order",
    [
        (
            {"field": "NAME", "direction": "ASC"},
            ["Collection1", "Collection2", "Collection3"],
        ),
        (
            {"field": "NAME", "direction": "DESC"},
            ["CollectionCollection2", "CollectionCollection1", "Collection3"],
        ),
        (
            {"field": "AVAILABILITY", "direction": "ASC"},
            ["Collection2", "CollectionCollection2", "Collection1"],
        ),
        (
            {"field": "ROOM_COUNT", "direction": "DESC"},
            ["CollectionCollection2", "Collection3", "CollectionCollection1"],
        ),
    ],
)
def test_collections_pagination_with_sorting(
    sort_by,
    collections_order,
    staff_api_client,
    permission_manage_rooms,
    collections_for_pagination,
    channel_USD,
):
    page_size = 3
    sort_by["channel"] = channel_USD.slug
    variables = {"first": page_size, "after": None, "sortBy": sort_by}
    response = staff_api_client.post_graphql(
        QUERY_COLLECTIONS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    collections_nodes = content["data"]["collections"]["edges"]
    assert collections_order[0] == collections_nodes[0]["node"]["name"]
    assert collections_order[1] == collections_nodes[1]["node"]["name"]
    assert collections_order[2] == collections_nodes[2]["node"]["name"]
    assert len(collections_nodes) == page_size


@pytest.mark.parametrize(
    "filter_by, collections_order",
    [
        (
            {"search": "CollectionCollection"},
            ["CollectionCollection1", "CollectionCollection2"],
        ),
        ({"search": "col_col"}, ["CollectionCollection1", "CollectionCollection2"]),
        ({"search": "Collection1"}, ["Collection1", "CollectionCollection1"]),
        ({"published": "HIDDEN"}, ["Collection2", "CollectionCollection2"]),
    ],
)
def test_collections_pagination_with_filtering(
    filter_by,
    collections_order,
    staff_api_client,
    permission_manage_rooms,
    collections_for_pagination,
    channel_USD,
):
    page_size = 2
    filter_by["channel"] = channel_USD.slug
    variables = {"first": page_size, "after": None, "filter": filter_by}
    response = staff_api_client.post_graphql(
        QUERY_COLLECTIONS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    collections_nodes = content["data"]["collections"]["edges"]
    assert collections_order[0] == collections_nodes[0]["node"]["name"]
    assert collections_order[1] == collections_nodes[1]["node"]["name"]
    assert len(collections_nodes) == page_size


@pytest.fixture
def rooms_for_pagination(
    room_type, color_attribute, category, hotel, channel_USD
):
    room_type2 = RoomType.objects.create(name="Apple")
    rooms = Room.objects.bulk_create(
        [
            Room(
                name="Room1",
                slug="prod1",
                category=category,
                room_type=room_type2,
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
                room_type=room_type2,
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
                room_type=room_type2,
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
            ),
            RoomChannelListing(
                room=rooms[1],
                channel=channel_USD,
                is_published=True,
                discounted_price_amount=Decimal(15),
            ),
            RoomChannelListing(
                room=rooms[2],
                channel=channel_USD,
                is_published=False,
                discounted_price_amount=Decimal(4),
            ),
            RoomChannelListing(
                room=rooms[3],
                channel=channel_USD,
                is_published=True,
                discounted_price_amount=Decimal(7),
            ),
        ]
    )

    room_attrib_values = color_attribute.values.all()
    associate_attribute_values_to_instance(
        rooms[1], color_attribute, room_attrib_values[0]
    )
    associate_attribute_values_to_instance(
        rooms[3], color_attribute, room_attrib_values[1]
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
        ]
    )
    Stock.objects.bulk_create(
        [
            Stock(hotel=hotel, room_variant=variants[0], quantity=100),
            Stock(hotel=hotel, room_variant=variants[1], quantity=0),
            Stock(hotel=hotel, room_variant=variants[2], quantity=0),
        ]
    )

    return rooms


QUERY_ROOMS_PAGINATION = """
    query (
        $first: Int, $last: Int, $after: String, $before: String,
        $sortBy: RoomOrder, $filter: RoomFilterInput
    ){
        rooms (
            first: $first, last: $last, after: $after, before: $before,
            sortBy: $sortBy, filter: $filter
        ) {
            edges {
                node {
                    name
                    slug
                }
            }
            pageInfo{
                startCursor
                endCursor
                hasNextPage
                hasPreviousPage
            }
        }
    }
"""


@pytest.mark.parametrize(
    "sort_by, rooms_order",
    [
        ({"field": "NAME", "direction": "ASC"}, ["Room1", "Room2", "Room3"]),
        (
            {"field": "NAME", "direction": "DESC"},
            ["RoomRoom2", "RoomRoom1", "Room3"],
        ),
        (
            {"field": "TYPE", "direction": "ASC"},
            ["Room1", "Room3", "RoomRoom2"],
        ),
    ],
)
def test_rooms_pagination_with_sorting(
    sort_by,
    rooms_order,
    staff_api_client,
    permission_manage_rooms,
    rooms_for_pagination,
):
    page_size = 3

    variables = {"first": page_size, "after": None, "sortBy": sort_by}
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    assert rooms_order[0] == rooms_nodes[0]["node"]["name"]
    assert rooms_order[1] == rooms_nodes[1]["node"]["name"]
    assert rooms_order[2] == rooms_nodes[2]["node"]["name"]
    assert len(rooms_nodes) == page_size


@pytest.mark.parametrize(
    "sort_by, rooms_order",
    [
        (
            {"field": "PUBLISHED", "direction": "ASC"},
            ["RoomRoom2", "Room1", "Room2"],
        ),
        (
            {"field": "PRICE", "direction": "ASC"},
            ["Room2", "RoomRoom2", "Room1"],
        ),
        (
            {"field": "MINIMAL_PRICE", "direction": "ASC"},
            ["RoomRoom2", "Room1", "Room2"],
        ),
    ],
)
def test_rooms_pagination_with_sorting_and_channel(
    sort_by,
    rooms_order,
    staff_api_client,
    permission_manage_rooms,
    rooms_for_pagination,
    channel_USD,
):
    page_size = 3

    sort_by["channel"] = channel_USD.slug
    variables = {"first": page_size, "after": None, "sortBy": sort_by}
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    assert rooms_order[0] == rooms_nodes[0]["node"]["name"]
    assert rooms_order[1] == rooms_nodes[1]["node"]["name"]
    assert rooms_order[2] == rooms_nodes[2]["node"]["name"]
    assert len(rooms_nodes) == page_size


def test_rooms_pagination_with_sorting_by_attribute(
    staff_api_client,
    permission_manage_rooms,
    rooms_for_pagination,
    color_attribute,
    channel_USD,
):
    page_size = 3
    rooms_order = ["Room2", "RoomRoom1", "Room1"]
    attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.id)

    sort_by = {"attributeId": attribute_id, "direction": "ASC"}
    variables = {"first": page_size, "after": None, "sortBy": sort_by}
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    assert rooms_order[0] == rooms_nodes[0]["node"]["name"]
    assert rooms_order[1] == rooms_nodes[1]["node"]["name"]
    assert rooms_order[2] == rooms_nodes[2]["node"]["name"]
    assert len(rooms_nodes) == page_size


def test_rooms_pagination_for_rooms_with_the_same_names_two_pages(
    staff_api_client, permission_manage_rooms, category, room_type, channel_USD
):
    rooms = Room.objects.bulk_create(
        [
            Room(
                name="Room",
                slug="prod-1",
                category=category,
                room_type=room_type,
            ),
            Room(
                name="Room",
                slug="prod-2",
                category=category,
                room_type=room_type,
            ),
            Room(
                name="Room",
                slug="prod-3",
                category=category,
                room_type=room_type,
            ),
        ]
    )
    page_size = 2
    variables = {"first": page_size, "after": None}

    response = staff_api_client.post_graphql(
        QUERY_ROOMS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    page_info = content["data"]["rooms"]["pageInfo"]

    assert len(rooms_nodes) == 2
    assert rooms_nodes[0]["node"]["slug"] == rooms[0].slug
    assert rooms_nodes[1]["node"]["slug"] == rooms[1].slug
    assert page_info["hasNextPage"] is True

    end_cursor = page_info["endCursor"]
    variables["after"] = end_cursor

    response = staff_api_client.post_graphql(
        QUERY_ROOMS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    page_info = content["data"]["rooms"]["pageInfo"]
    assert len(rooms_nodes) == 1
    assert rooms_nodes[0]["node"]["slug"] == rooms[2].slug
    assert page_info["hasNextPage"] is False


def test_rooms_pagination_for_rooms_with_the_same_names_one_page(
    staff_api_client, permission_manage_rooms, category, room_type, channel_USD
):
    rooms = Room.objects.bulk_create(
        [
            Room(
                name="Room",
                slug="prod-1",
                category=category,
                room_type=room_type,
            ),
            Room(
                name="Room",
                slug="prod-2",
                category=category,
                room_type=room_type,
            ),
            Room(
                name="Room",
                slug="prod-3",
                category=category,
                room_type=room_type,
            ),
        ]
    )
    page_size = 3
    variables = {"first": page_size, "after": None}

    response = staff_api_client.post_graphql(
        QUERY_ROOMS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    page_info = content["data"]["rooms"]["pageInfo"]

    assert len(rooms_nodes) == 3
    assert rooms_nodes[0]["node"]["slug"] == rooms[0].slug
    assert rooms_nodes[1]["node"]["slug"] == rooms[1].slug
    assert rooms_nodes[2]["node"]["slug"] == rooms[2].slug
    assert page_info["hasNextPage"] is False


@pytest.mark.parametrize(
    "filter_by, rooms_order",
    [
        ({"hasCategory": True}, ["Room1", "Room2"]),
        ({"stockAvailability": "OUT_OF_STOCK"}, ["RoomRoom1", "RoomRoom2"]),
    ],
)
def test_rooms_pagination_with_filtering(
    filter_by,
    rooms_order,
    staff_api_client,
    permission_manage_rooms,
    rooms_for_pagination,
):
    page_size = 2

    variables = {"first": page_size, "after": None, "filter": filter_by}
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    assert rooms_order[0] == rooms_nodes[0]["node"]["name"]
    assert rooms_order[1] == rooms_nodes[1]["node"]["name"]
    assert len(rooms_nodes) == page_size


@pytest.mark.parametrize(
    "filter_by, rooms_order",
    [
        ({"isPublished": True}, ["Room1", "Room2"]),
        ({"price": {"gte": 8, "lte": 12}}, ["Room1", "RoomRoom2"]),
    ],
)
def test_rooms_pagination_with_filtering_and_channel(
    filter_by,
    rooms_order,
    staff_api_client,
    permission_manage_rooms,
    rooms_for_pagination,
    channel_USD,
):
    page_size = 2

    filter_by["channel"] = channel_USD.slug
    variables = {"first": page_size, "after": None, "filter": filter_by}
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    assert rooms_order[0] == rooms_nodes[0]["node"]["name"]
    assert rooms_order[1] == rooms_nodes[1]["node"]["name"]
    assert len(rooms_nodes) == page_size


def test_rooms_pagination_with_filtering_by_attribute(
    staff_api_client, permission_manage_rooms, rooms_for_pagination, channel_USD
):
    page_size = 2
    rooms_order = ["Room2", "RoomRoom1"]
    filter_by = {"attributes": [{"slug": "color", "values": ["red", "blue"]}]}

    variables = {"first": page_size, "after": None, "filter": filter_by}
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    assert rooms_order[0] == rooms_nodes[0]["node"]["name"]
    assert rooms_order[1] == rooms_nodes[1]["node"]["name"]
    assert len(rooms_nodes) == page_size


def test_rooms_pagination_with_filtering_by_room_types(
    staff_api_client,
    permission_manage_rooms,
    rooms_for_pagination,
    room_type,
    channel_USD,
):
    page_size = 2
    rooms_order = ["Room2", "RoomRoom1"]
    room_type_id = graphene.Node.to_global_id("RoomType", room_type.id)
    filter_by = {"roomTypes": [room_type_id]}

    variables = {"first": page_size, "after": None, "filter": filter_by}
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    assert rooms_order[0] == rooms_nodes[0]["node"]["name"]
    assert rooms_order[1] == rooms_nodes[1]["node"]["name"]
    assert len(rooms_nodes) == page_size


def test_rooms_pagination_with_filtering_by_stocks(
    staff_api_client,
    permission_manage_rooms,
    rooms_for_pagination,
    hotel,
    channel_USD,
):
    page_size = 2
    rooms_order = ["RoomRoom1", "RoomRoom2"]
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.id)
    filter_by = {"stocks": {"hotelIds": [hotel_id], "quantity": {"lte": 10}}}

    variables = {"first": page_size, "after": None, "filter": filter_by}
    response = staff_api_client.post_graphql(
        QUERY_ROOMS_PAGINATION,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["rooms"]["edges"]
    assert rooms_order[0] == rooms_nodes[0]["node"]["name"]
    assert rooms_order[1] == rooms_nodes[1]["node"]["name"]
    assert len(rooms_nodes) == page_size


@pytest.fixture
def room_types_for_pagination(db):
    return RoomType.objects.bulk_create(
        [
            RoomType(
                name="RoomType1",
                slug="pt1",
                is_digital=True,
                is_shipping_required=False,
            ),
            RoomType(
                name="RoomTypeRoomType1",
                slug="pt_pt1",
                is_digital=False,
                is_shipping_required=False,
            ),
            RoomType(
                name="RoomTypeRoomType2",
                slug="pt_pt2",
                is_digital=False,
                is_shipping_required=True,
            ),
            RoomType(
                name="RoomType2",
                slug="pt2",
                is_digital=False,
                is_shipping_required=True,
                has_variants=False,
            ),
            RoomType(
                name="RoomType3",
                slug="pt3",
                is_digital=True,
                is_shipping_required=False,
                has_variants=False,
            ),
        ]
    )


QUERY_ROOM_TYPES_PAGINATION = """
    query (
        $first: Int, $last: Int, $after: String, $before: String,
        $sortBy: RoomTypeSortingInput, $filter: RoomTypeFilterInput
    ){
        roomTypes (
            first: $first, last: $last, after: $after, before: $before,
            sortBy: $sortBy, filter: $filter
        ) {
            edges {
                node {
                    name
                }
            }
            pageInfo{
                startCursor
                endCursor
                hasNextPage
                hasPreviousPage
            }
        }
    }
"""


@pytest.mark.parametrize(
    "sort_by, room_types_order",
    [
        (
            {"field": "NAME", "direction": "ASC"},
            ["RoomType1", "RoomType2", "RoomType3"],
        ),
        (
            {"field": "NAME", "direction": "DESC"},
            ["RoomTypeRoomType2", "RoomTypeRoomType1", "RoomType3"],
        ),
        (
            {"field": "DIGITAL", "direction": "ASC"},
            ["RoomType2", "RoomTypeRoomType1", "RoomTypeRoomType2"],
        ),
        (
            {"field": "SHIPPING_REQUIRED", "direction": "ASC"},
            ["RoomType1", "RoomType3", "RoomTypeRoomType1"],
        ),
    ],
)
def test_room_types_pagination_with_sorting(
    sort_by,
    room_types_order,
    staff_api_client,
    room_types_for_pagination,
):
    page_size = 3

    variables = {"first": page_size, "after": None, "sortBy": sort_by}
    response = staff_api_client.post_graphql(QUERY_ROOM_TYPES_PAGINATION, variables)
    content = get_graphql_content(response)
    room_types_nodes = content["data"]["roomTypes"]["edges"]
    assert room_types_order[0] == room_types_nodes[0]["node"]["name"]
    assert room_types_order[1] == room_types_nodes[1]["node"]["name"]
    assert room_types_order[2] == room_types_nodes[2]["node"]["name"]
    assert len(room_types_nodes) == page_size


@pytest.mark.parametrize(
    "filter_by, room_types_order",
    [
        (
            {"search": "RoomTypeRoomType"},
            ["RoomTypeRoomType1", "RoomTypeRoomType2"],
        ),
        ({"search": "RoomType1"}, ["RoomType1", "RoomTypeRoomType1"]),
        ({"search": "pt_pt"}, ["RoomTypeRoomType1", "RoomTypeRoomType2"]),
        (
            {"roomType": "DIGITAL"},
            ["RoomType1", "RoomType3"],
        ),
        ({"roomType": "SHIPPABLE"}, ["RoomType2", "RoomTypeRoomType2"]),
        ({"configurable": "CONFIGURABLE"}, ["RoomType1", "RoomTypeRoomType1"]),
        ({"configurable": "SIMPLE"}, ["RoomType2", "RoomType3"]),
    ],
)
def test_room_types_pagination_with_filtering(
    filter_by,
    room_types_order,
    staff_api_client,
    room_types_for_pagination,
):
    page_size = 2

    variables = {"first": page_size, "after": None, "filter": filter_by}
    response = staff_api_client.post_graphql(
        QUERY_ROOM_TYPES_PAGINATION,
        variables,
    )
    content = get_graphql_content(response)
    room_types_nodes = content["data"]["roomTypes"]["edges"]
    assert room_types_order[0] == room_types_nodes[0]["node"]["name"]
    assert room_types_order[1] == room_types_nodes[1]["node"]["name"]
    assert len(room_types_nodes) == page_size
