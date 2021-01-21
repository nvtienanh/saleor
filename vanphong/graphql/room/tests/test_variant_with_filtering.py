import pytest

from ....room.models import Room, RoomVariant
from ...tests.utils import get_graphql_content

QUERY_VARIANTS_FILTER = """
query variants($filter: RoomVariantFilterInput){
    roomVariants(first:10, filter: $filter){
        edges{
            node{
                name
                sku
            }
        }
    }
}
"""


@pytest.fixture
def rooms_for_variant_filtering(room_type, category):
    rooms = Room.objects.bulk_create(
        [
            Room(
                name="Room1",
                slug="prod1",
                category=category,
                room_type=room_type,
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
            ),
            Room(
                name="Room3",
                slug="prod3",
                category=category,
                room_type=room_type,
            ),
        ]
    )
    RoomVariant.objects.bulk_create(
        [
            RoomVariant(
                room=rooms[0],
                sku="P1-V1",
            ),
            RoomVariant(
                room=rooms[0],
                sku="P1-V2",
            ),
            RoomVariant(room=rooms[1], sku="PP1-V1", name="XL"),
            RoomVariant(room=rooms[2], sku="PP2-V1", name="XXL"),
            RoomVariant(
                room=rooms[3],
                sku="P2-V1",
            ),
            RoomVariant(
                room=rooms[4],
                sku="P3-V1",
            ),
        ]
    )
    return rooms


@pytest.mark.parametrize(
    "filter_by, variants",
    [
        ({"search": "Room1"}, ["P1-V1", "P1-V2", "PP1-V1"]),
        ({"search": "Room3"}, ["P3-V1"]),
        ({"search": "XL"}, ["PP1-V1", "PP2-V1"]),
        ({"search": "XXL"}, ["PP2-V1"]),
        ({"search": "PP2-V1"}, ["PP2-V1"]),
        ({"search": "P1"}, ["P1-V1", "P1-V2", "PP1-V1"]),
        ({"search": ["invalid"]}, []),
        ({"sku": ["P1"]}, []),
        ({"sku": ["P1-V1", "P1-V2", "PP1-V1"]}, ["P1-V1", "P1-V2", "PP1-V1"]),
        ({"sku": ["PP1-V1", "PP2-V1"]}, ["PP1-V1", "PP2-V1"]),
        ({"sku": ["invalid"]}, []),
    ],
)
def test_rooms_pagination_with_filtering(
    filter_by,
    variants,
    staff_api_client,
    permission_manage_rooms,
    rooms_for_variant_filtering,
):
    # given
    variables = {"filter": filter_by}

    # when
    response = staff_api_client.post_graphql(
        QUERY_VARIANTS_FILTER,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    rooms_nodes = content["data"]["roomVariants"]["edges"]
    for index, variant_sku in enumerate(variants):
        assert variant_sku == rooms_nodes[index]["node"]["sku"]
    assert len(variants) == len(rooms_nodes)
