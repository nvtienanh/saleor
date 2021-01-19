import graphene
import pytest

from ....tests.utils import get_graphql_content

SHIPPING_METHODS_QUERY = """
query GetShippingMethods($channel: String) {
  shippingZones(first: 10, channel: $channel) {
    edges {
      node {
        shippingMethods {
          id
          name
          minimumOrderWeight {
            unit
            value
          }
          maximumOrderWeight {
            unit
            value
          }
          type
          channelListings {
            id
            channel {
              id
              name
            }
          }
          price {
            amount
            currency
          }
          maximumOrderPrice {
            currency
            amount
          }
          minimumOrderPrice {
            currency
            amount
          }
        }
      }
    }
  }
}
"""


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_vouchers_query_with_channel_slug(
    staff_api_client,
    shipping_zones,
    channel_USD,
    permission_manage_shipping,
    count_queries,
):
    variables = {"channel": channel_USD.slug}
    get_graphql_content(
        staff_api_client.post_graphql(
            SHIPPING_METHODS_QUERY,
            variables,
            permissions=[permission_manage_shipping],
            check_no_permissions=False,
        )
    )


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_vouchers_query_without_channel_slug(
    staff_api_client,
    shipping_zones,
    permission_manage_shipping,
    count_queries,
):
    get_graphql_content(
        staff_api_client.post_graphql(
            SHIPPING_METHODS_QUERY,
            {},
            permissions=[permission_manage_shipping],
            check_no_permissions=False,
        )
    )


EXCLUDE_ROOMS_MUTATION = """
    mutation shippingPriceRemoveRoomFromExclude(
        $id: ID!, $input:ShippingPriceExcludeRoomsInput!
        ) {
        shippingPriceExcludeRooms(
            id: $id
            input: $input) {
            shippingErrors {
                field
                code
            }
            shippingMethod {
                id
                excludedRooms(first:10){
                   totalCount
                   edges{
                     node{
                       id
                     }
                   }
                }
            }
        }
    }
"""


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_exclude_rooms_for_shipping_method(
    shipping_method,
    published_collection,
    room_list_published,
    room_list,
    categories_tree_with_published_rooms,
    collection,
    staff_api_client,
    permission_manage_shipping,
):
    # room_list has rooms with slugs slug:test-room-a, slug:test-room-b,
    # slug:test-room-c
    room_db_ids = [p.pk for p in room_list]
    room_ids = [graphene.Node.to_global_id("Room", p) for p in room_db_ids]

    expected_room_ids = [
        graphene.Node.to_global_id("Room", p.pk) for p in room_list
    ]

    shipping_method_id = graphene.Node.to_global_id(
        "ShippingMethod", shipping_method.pk
    )
    variables = {
        "id": shipping_method_id,
        "input": {"rooms": room_ids},
    }

    response = staff_api_client.post_graphql(
        EXCLUDE_ROOMS_MUTATION, variables, permissions=[permission_manage_shipping]
    )

    content = get_graphql_content(response)
    shipping_method = content["data"]["shippingPriceExcludeRooms"]["shippingMethod"]
    excluded_rooms = shipping_method["excludedRooms"]
    total_count = excluded_rooms["totalCount"]
    excluded_room_ids = {p["node"]["id"] for p in excluded_rooms["edges"]}
    assert len(expected_room_ids) == total_count == 3
    assert excluded_room_ids == set(expected_room_ids)


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_exclude_rooms_for_shipping_method_already_has_excluded_rooms(
    shipping_method,
    room_list,
    room,
    staff_api_client,
    permission_manage_shipping,
):
    shipping_method_id = graphene.Node.to_global_id(
        "ShippingMethod", shipping_method.pk
    )
    shipping_method.excluded_rooms.add(room, room_list[0])
    room_ids = [graphene.Node.to_global_id("Room", p.pk) for p in room_list]
    variables = {"id": shipping_method_id, "input": {"rooms": room_ids}}
    response = staff_api_client.post_graphql(
        EXCLUDE_ROOMS_MUTATION, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    shipping_method = content["data"]["shippingPriceExcludeRooms"]["shippingMethod"]
    excluded_rooms = shipping_method["excludedRooms"]
    total_count = excluded_rooms["totalCount"]
    expected_room_ids = room_ids
    expected_room_ids.append(graphene.Node.to_global_id("Room", room.pk))
    excluded_room_ids = {p["node"]["id"] for p in excluded_rooms["edges"]}
    assert len(expected_room_ids) == total_count
    assert excluded_room_ids == set(expected_room_ids)


REMOVE_ROOMS_FROM_EXCLUDED_ROOMS_MUTATION = """
    mutation shippingPriceRemoveRoomFromExclude(
        $id: ID!, $rooms: [ID]!
        ) {
        shippingPriceRemoveRoomFromExclude(
            id: $id
            rooms: $rooms) {
            shippingErrors {
                field
                code
            }
            shippingMethod {
                id
                excludedRooms(first:10){
                   totalCount
                   edges{
                     node{
                       id
                     }
                   }
                }
            }
        }
    }
"""


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_remove_rooms_from_excluded_rooms_for_shipping_method(
    shipping_method,
    room_list,
    staff_api_client,
    permission_manage_shipping,
    room,
):
    shipping_method_id = graphene.Node.to_global_id(
        "ShippingMethod", shipping_method.pk
    )
    shipping_method.excluded_rooms.set(room_list)
    shipping_method.excluded_rooms.add(room)

    room_ids = [
        graphene.Node.to_global_id("Room", room.pk),
    ]
    variables = {"id": shipping_method_id, "rooms": room_ids}
    response = staff_api_client.post_graphql(
        REMOVE_ROOMS_FROM_EXCLUDED_ROOMS_MUTATION,
        variables,
        permissions=[permission_manage_shipping],
    )

    content = get_graphql_content(response)
    shipping_method = content["data"]["shippingPriceRemoveRoomFromExclude"][
        "shippingMethod"
    ]
    excluded_rooms = shipping_method["excludedRooms"]
    total_count = excluded_rooms["totalCount"]
    expected_room_ids = {
        graphene.Node.to_global_id("Room", p.pk) for p in room_list
    }
    excluded_room_ids = {p["node"]["id"] for p in excluded_rooms["edges"]}
    assert total_count == len(expected_room_ids)
    assert excluded_room_ids == expected_room_ids
