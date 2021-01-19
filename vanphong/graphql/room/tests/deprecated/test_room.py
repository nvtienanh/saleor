import warnings

import graphene

from .....channel.utils import DEPRECATION_WARNING_MESSAGE
from .....room.models import Room
from ....tests.utils import get_graphql_content

QUERY_ROOM = """
    query ($id: ID, $slug: String){
        room(
            id: $id,
            slug: $slug,
        ) {
            id
            name
        }
    }
    """

QUERY_FETCH_ALL_ROOMS = """
    query {
        rooms(first: 1) {
            totalCount
            edges {
                node {
                    name
                    isAvailable
                    availableForPurchase
                    isAvailableForPurchase
                }
            }
        }
    }
"""


def test_room_query_by_id_with_default_channel(user_api_client, room):
    variables = {"id": graphene.Node.to_global_id("Room", room.pk)}

    with warnings.catch_warnings(record=True) as warns:
        response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)
        content = get_graphql_content(response)
    collection_data = content["data"]["room"]
    assert collection_data is not None
    assert collection_data["name"] == room.name
    assert any(
        [str(warning.message) == DEPRECATION_WARNING_MESSAGE for warning in warns]
    )


def test_room_query_by_slug_with_default_channel(user_api_client, room):
    variables = {"slug": room.slug}
    with warnings.catch_warnings(record=True) as warns:
        response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)
        content = get_graphql_content(response)
    collection_data = content["data"]["room"]
    assert collection_data is not None
    assert collection_data["name"] == room.name
    assert any(
        [str(warning.message) == DEPRECATION_WARNING_MESSAGE for warning in warns]
    )


def test_fetch_all_rooms(user_api_client, room):
    with warnings.catch_warnings(record=True) as warns:
        response = user_api_client.post_graphql(QUERY_FETCH_ALL_ROOMS)
        content = get_graphql_content(response)
    room_channel_listing = room.channel_listings.get()
    num_rooms = Room.objects.count()
    data = content["data"]["rooms"]
    room_data = data["edges"][0]["node"]
    assert data["totalCount"] == num_rooms
    assert room_data["isAvailable"] is True
    assert room_data["isAvailableForPurchase"] is True
    assert room_data["availableForPurchase"] == str(
        room_channel_listing.available_for_purchase
    )
    assert len(content["data"]["rooms"]["edges"]) == num_rooms
    assert any(
        [str(warning.message) == DEPRECATION_WARNING_MESSAGE for warning in warns]
    )


QUERY_COLLECTION_FROM_ROOM = """
    query ($id: ID, $channel:String){
        room(
            id: $id,
            channel: $channel
        ) {
            collections {
                name
            }
        }
    }
    """


def test_get_collections_from_room_as_customer(
    user_api_client, room_with_collections, channel_USD, published_collection
):
    # given
    room = room_with_collections
    variables = {"id": graphene.Node.to_global_id("Room", room.pk)}

    # when
    with warnings.catch_warnings(record=True) as warns:
        response = user_api_client.post_graphql(
            QUERY_COLLECTION_FROM_ROOM,
            variables=variables,
            permissions=(),
            check_no_permissions=False,
        )

    # then
    content = get_graphql_content(response)
    collections = content["data"]["room"]["collections"]
    assert len(collections) == 1
    assert {"name": published_collection.name} in collections
    assert any(
        [str(warning.message) == DEPRECATION_WARNING_MESSAGE for warning in warns]
    )


def test_get_collections_from_room_as_anonymous(
    api_client, room_with_collections, channel_USD, published_collection
):
    # given
    room = room_with_collections
    variables = {"id": graphene.Node.to_global_id("Room", room.pk)}

    # when
    with warnings.catch_warnings(record=True) as warns:
        response = api_client.post_graphql(
            QUERY_COLLECTION_FROM_ROOM,
            variables=variables,
            permissions=(),
            check_no_permissions=False,
        )

    # then
    content = get_graphql_content(response)
    collections = content["data"]["room"]["collections"]
    assert len(collections) == 1
    assert {"name": published_collection.name} in collections
    assert any(
        [str(warning.message) == DEPRECATION_WARNING_MESSAGE for warning in warns]
    )
