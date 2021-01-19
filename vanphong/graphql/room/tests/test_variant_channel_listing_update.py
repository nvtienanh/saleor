from unittest.mock import patch

import graphene

from ....room.error_codes import RoomErrorCode
from ....room.models import RoomChannelListing
from ...tests.utils import (
    assert_negative_positive_decimal_value,
    assert_no_permission,
    get_graphql_content,
)

ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION = """
mutation UpdateRoomVariantChannelListing(
    $id: ID!,
    $input: [RoomVariantChannelListingAddInput!]!
) {
    roomVariantChannelListingUpdate(id: $id, input: $input) {
        roomChannelListingErrors {
            field
            message
            code
            channels
        }
        variant {
            id
            channelListings {
                channel {
                    id
                    slug
                    currencyCode
                }
                price {
                    amount
                    currency
                }
                costPrice {
                    amount
                    currency
                }
                margin
            }
        }
    }
}
"""


def test_variant_channel_listing_update_duplicated_channel(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": variant_id,
        "input": [
            {"channelId": channel_id, "price": 1},
            {"channelId": channel_id, "price": 2},
        ],
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    errors = content["data"]["roomVariantChannelListingUpdate"][
        "roomChannelListingErrors"
    ]
    assert len(errors) == 1
    assert errors[0]["field"] == "channelId"
    assert errors[0]["code"] == RoomErrorCode.DUPLICATED_INPUT_ITEM.name
    assert errors[0]["channels"] == [channel_id]


def test_variant_channel_listing_update_with_empty_input(
    staff_api_client, room, permission_manage_rooms
):
    # given
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    variables = {
        "id": variant_id,
        "input": [],
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    errors = content["data"]["roomVariantChannelListingUpdate"][
        "roomChannelListingErrors"
    ]
    assert not errors


def test_variant_channel_listing_update_not_assigned_channel(
    staff_api_client, room, permission_manage_rooms, channel_PLN
):
    # given
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    variables = {
        "id": variant_id,
        "input": [{"channelId": channel_id, "price": 1}],
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    errors = content["data"]["roomVariantChannelListingUpdate"][
        "roomChannelListingErrors"
    ]
    assert len(errors) == 1
    assert errors[0]["field"] == "input"
    assert errors[0]["code"] == RoomErrorCode.ROOM_NOT_ASSIGNED_TO_CHANNEL.name
    assert errors[0]["channels"] == [channel_id]


def test_variant_channel_listing_update_negative_price(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": variant_id,
        "input": [{"channelId": channel_id, "price": -1}],
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION, variables=variables
    )

    # then
    assert_negative_positive_decimal_value(response)


def test_variant_channel_listing_update_with_too_many_decimal_places_in_price(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": variant_id,
        "input": [{"channelId": channel_id, "price": 1.1234}],
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    error = content["data"]["roomVariantChannelListingUpdate"][
        "roomChannelListingErrors"
    ][0]
    assert error["field"] == "price"
    assert error["code"] == RoomErrorCode.INVALID.name


def test_variant_channel_listing_update_as_staff_user(
    staff_api_client, room, permission_manage_rooms, channel_USD, channel_PLN
):
    # given
    RoomChannelListing.objects.create(
        room=room,
        channel=channel_PLN,
        is_published=True,
    )
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_usd_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    channel_pln_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    price = 1
    second_price = 20
    variables = {
        "id": variant_id,
        "input": [
            {"channelId": channel_usd_id, "price": price, "costPrice": price},
            {
                "channelId": channel_pln_id,
                "price": second_price,
                "costPrice": second_price,
            },
        ],
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomVariantChannelListingUpdate"]
    variant_data = data["variant"]
    assert not data["roomChannelListingErrors"]
    assert variant_data["id"] == variant_id
    assert variant_data["channelListings"][0]["price"]["currency"] == "USD"
    assert variant_data["channelListings"][0]["price"]["amount"] == price
    assert variant_data["channelListings"][0]["costPrice"]["amount"] == price
    assert variant_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert variant_data["channelListings"][1]["price"]["currency"] == "PLN"
    assert variant_data["channelListings"][1]["price"]["amount"] == second_price
    assert variant_data["channelListings"][1]["costPrice"]["amount"] == second_price
    assert variant_data["channelListings"][1]["channel"]["slug"] == channel_PLN.slug


@patch("saleor.plugins.manager.PluginsManager.room_updated")
def test_variant_channel_listing_update_trigger_webhook_room_updated(
    mock_room_updated,
    staff_api_client,
    room,
    permission_manage_rooms,
    channel_USD,
    channel_PLN,
):
    # given
    RoomChannelListing.objects.create(
        room=room,
        channel=channel_PLN,
        is_published=True,
    )
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_usd_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    channel_pln_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    price = 1
    second_price = 20
    variables = {
        "id": variant_id,
        "input": [
            {"channelId": channel_usd_id, "price": price, "costPrice": price},
            {
                "channelId": channel_pln_id,
                "price": second_price,
                "costPrice": second_price,
            },
        ],
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    get_graphql_content(response)

    # then
    mock_room_updated.assert_called_once_with(room)


def test_variant_channel_listing_update_as_app(
    app_api_client, room, permission_manage_rooms, channel_USD, channel_PLN
):
    # given
    RoomChannelListing.objects.create(
        room=room,
        channel=channel_PLN,
        is_published=True,
    )
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_usd_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    channel_pln_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    variables = {
        "id": variant_id,
        "input": [
            {"channelId": channel_usd_id, "price": 1},
            {"channelId": channel_pln_id, "price": 20},
        ],
    }

    # when
    response = app_api_client.post_graphql(
        ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomVariantChannelListingUpdate"]
    variant_data = data["variant"]
    assert not data["roomChannelListingErrors"]
    assert variant_data["id"] == variant_id
    assert variant_data["channelListings"][0]["price"]["currency"] == "USD"
    assert variant_data["channelListings"][0]["price"]["amount"] == 1
    assert variant_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert variant_data["channelListings"][1]["price"]["currency"] == "PLN"
    assert variant_data["channelListings"][1]["price"]["amount"] == 20
    assert variant_data["channelListings"][1]["channel"]["slug"] == channel_PLN.slug


def test_variant_channel_listing_update_as_customer(
    user_api_client, room, channel_USD, channel_PLN
):
    # given
    RoomChannelListing.objects.create(
        room=room,
        channel=channel_PLN,
        is_published=True,
    )
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_usd_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    channel_pln_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    variables = {
        "id": variant_id,
        "input": [
            {"channelId": channel_usd_id, "price": 1},
            {"channelId": channel_pln_id, "price": 20},
        ],
    }

    # when
    response = user_api_client.post_graphql(
        ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
    )

    # then
    assert_no_permission(response)


def test_variant_channel_listing_update_as_anonymous(
    api_client, room, channel_USD, channel_PLN
):
    # given
    RoomChannelListing.objects.create(
        room=room,
        channel=channel_PLN,
        is_published=True,
    )
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_usd_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    channel_pln_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    variables = {
        "id": variant_id,
        "input": [
            {"channelId": channel_usd_id, "price": 1},
            {"channelId": channel_pln_id, "price": 20},
        ],
    }

    # when
    response = api_client.post_graphql(
        ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
    )

    # then
    assert_no_permission(response)


@patch("saleor.graphql.room.mutations.channels.update_room_discounted_price_task")
def test_room_variant_channel_listing_update_updates_discounted_price(
    mock_update_room_discounted_price_task,
    staff_api_client,
    room,
    permission_manage_rooms,
    channel_USD,
):
    query = ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)

    variables = {
        "id": variant_id,
        "input": [{"channelId": channel_id, "price": "1.99"}],
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    assert response.status_code == 200

    content = get_graphql_content(response)
    data = content["data"]["roomVariantChannelListingUpdate"]
    assert data["roomChannelListingErrors"] == []

    mock_update_room_discounted_price_task.delay.assert_called_once_with(room.pk)


def test_room_variant_channel_listing_update_remove_cost_price(
    staff_api_client,
    room,
    permission_manage_rooms,
    channel_USD,
):
    # given
    query = ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": variant_id,
        "input": [{"channelId": channel_id, "price": 1, "costPrice": None}],
    }

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomVariantChannelListingUpdate"]
    variant_data = data["variant"]
    assert not data["roomChannelListingErrors"]
    assert variant_data["id"] == variant_id
    assert variant_data["channelListings"][0]["price"]["currency"] == "USD"
    assert variant_data["channelListings"][0]["price"]["amount"] == 1
    assert not variant_data["channelListings"][0]["costPrice"]
    assert variant_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug


def test_room_channel_listing_update_too_many_decimal_places_in_cost_price(
    app_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_usd_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": variant_id,
        "input": [{"channelId": channel_usd_id, "costPrice": 1.03321, "price": 1}],
    }

    # when
    response = app_api_client.post_graphql(
        ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomVariantChannelListingUpdate"]
    assert data["roomChannelListingErrors"][0]["field"] == "costPrice"
    assert (
        data["roomChannelListingErrors"][0]["code"] == RoomErrorCode.INVALID.name
    )


def test_room_channel_listing_update_invalid_cost_price(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    variant = room.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": variant_id,
        "input": [{"channelId": channel_id, "costPrice": -1, "price": 1}],
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_CHANNEL_LISTING_UPDATE_MUTATION, variables=variables
    )

    # then
    assert_negative_positive_decimal_value(response)
