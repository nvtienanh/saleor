import random
from datetime import date, timedelta

import graphene
import pytest
from freezegun import freeze_time

from ....room.models import Room, RoomChannelListing
from ...tests.utils import get_graphql_content

COLLECTION_RESORT_QUERY = """
mutation ReorderCollectionRooms($collectionId: ID!, $moves: [MoveRoomInput]!) {
  collectionReorderRooms(collectionId: $collectionId, moves: $moves) {
    collection {
      id
      rooms(first: 10, sortBy:{field:COLLECTION, direction:ASC}) {
        edges {
          node {
            name
            id
          }
        }
      }
    }
    errors {
      field
      message
    }
  }
}
"""


def test_sort_rooms_within_collection_invalid_collection_id(
    staff_api_client, collection, room, permission_manage_rooms
):
    collection_id = graphene.Node.to_global_id("Collection", -1)
    room_id = graphene.Node.to_global_id("Room", room.pk)

    moves = [{"roomId": room_id, "sortOrder": 1}]

    content = get_graphql_content(
        staff_api_client.post_graphql(
            COLLECTION_RESORT_QUERY,
            {"collectionId": collection_id, "moves": moves},
            permissions=[permission_manage_rooms],
        )
    )["data"]["collectionReorderRooms"]

    assert content["errors"] == [
        {
            "field": "collectionId",
            "message": f"Couldn't resolve to a collection: {collection_id}",
        }
    ]


def test_sort_rooms_within_collection_invalid_room_id(
    staff_api_client, collection, room, permission_manage_rooms
):
    # Remove the rooms from the collection to make the room invalid
    collection.rooms.clear()
    collection_id = graphene.Node.to_global_id("Collection", collection.pk)

    # The move should be targeting an invalid room
    room_id = graphene.Node.to_global_id("Room", room.pk)
    moves = [{"roomId": room_id, "sortOrder": 1}]

    content = get_graphql_content(
        staff_api_client.post_graphql(
            COLLECTION_RESORT_QUERY,
            {"collectionId": collection_id, "moves": moves},
            permissions=[permission_manage_rooms],
        )
    )["data"]["collectionReorderRooms"]

    assert content["errors"] == [
        {"field": "moves", "message": f"Couldn't resolve to a room: {room_id}"}
    ]


def test_sort_rooms_within_collection(
    staff_api_client,
    staff_user,
    published_collection,
    collection_with_rooms,
    permission_manage_rooms,
    channel_USD,
):

    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    collection_id = graphene.Node.to_global_id("Collection", published_collection.pk)

    rooms = collection_with_rooms
    room = graphene.Node.to_global_id("Room", rooms[0].pk)
    second_room = graphene.Node.to_global_id("Room", rooms[1].pk)
    third_room = graphene.Node.to_global_id("Room", rooms[2].pk)

    variables = {
        "collectionId": collection_id,
        "moves": [{"roomId": room, "sortOrder": -1}],
    }

    content = get_graphql_content(
        staff_api_client.post_graphql(COLLECTION_RESORT_QUERY, variables)
    )["data"]["collectionReorderRooms"]
    assert not content["errors"]

    assert content["collection"]["id"] == collection_id

    rooms = content["collection"]["rooms"]["edges"]
    assert rooms[0]["node"]["id"] == room
    assert rooms[1]["node"]["id"] == third_room
    assert rooms[2]["node"]["id"] == second_room

    variables = {
        "collectionId": collection_id,
        "moves": [
            {"roomId": room, "sortOrder": 1},
            {"roomId": second_room, "sortOrder": -1},
        ],
    }
    content = get_graphql_content(
        staff_api_client.post_graphql(COLLECTION_RESORT_QUERY, variables)
    )["data"]["collectionReorderRooms"]

    rooms = content["collection"]["rooms"]["edges"]
    assert rooms[0]["node"]["id"] == third_room
    assert rooms[1]["node"]["id"] == second_room
    assert rooms[2]["node"]["id"] == room


GET_SORTED_ROOMS_QUERY = """
query Rooms($sortBy: RoomOrder, $channel: String) {
    rooms(first: 10, sortBy: $sortBy, channel: $channel) {
      edges {
        node {
          id
        }
      }
    }
}
"""


@freeze_time("2020-03-18 12:00:00")
@pytest.mark.parametrize(
    "direction, order_direction",
    (("ASC", "publication_date"), ("DESC", "-publication_date")),
)
def test_sort_rooms_by_publication_date(
    direction, order_direction, api_client, room_list, channel_USD
):
    room_channel_listings = []
    for iter_value, room in enumerate(room_list):
        room_channel_listing = room.channel_listings.get(channel=channel_USD)
        room_channel_listing.publication_date = date.today() - timedelta(
            days=iter_value
        )
        room_channel_listings.append(room_channel_listing)
    RoomChannelListing.objects.bulk_update(
        room_channel_listings, ["publication_date"]
    )

    variables = {
        "sortBy": {
            "direction": direction,
            "field": "PUBLICATION_DATE",
            "channel": channel_USD.slug,
        },
        "channel": channel_USD.slug,
    }

    # when
    response = api_client.post_graphql(GET_SORTED_ROOMS_QUERY, variables)

    # then
    content = get_graphql_content(response)
    data = content["data"]["rooms"]["edges"]

    if direction == "ASC":
        room_list.reverse()

    assert [node["node"]["id"] for node in data] == [
        graphene.Node.to_global_id("Room", room.pk) for room in room_list
    ]


@pytest.mark.parametrize(
    "direction, order_direction",
    (("ASC", "rating"), ("DESC", "-rating")),
)
def test_sort_rooms_by_rating(
    direction, order_direction, api_client, room_list, channel_USD
):

    for room in room_list:
        room.rating = random.uniform(1, 10)
    Room.objects.bulk_update(room_list, ["rating"])

    variables = {
        "sortBy": {"direction": direction, "field": "RATING"},
        "channel": channel_USD.slug,
    }

    # when
    response = api_client.post_graphql(GET_SORTED_ROOMS_QUERY, variables)

    # then
    content = get_graphql_content(response)
    data = content["data"]["rooms"]["edges"]

    sorted_rooms = Room.objects.order_by(order_direction)
    expected_ids = [
        graphene.Node.to_global_id("Room", room.pk) for room in sorted_rooms
    ]
    assert [node["node"]["id"] for node in data] == expected_ids
