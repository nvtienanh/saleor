import datetime
from unittest.mock import patch

import graphene
from freezegun import freeze_time

from ....room.error_codes import RoomErrorCode
from ....room.utils.costs import get_room_costs_data
from ...tests.utils import assert_no_permission, get_graphql_content

ROOM_CHANNEL_LISTING_UPDATE_MUTATION = """
mutation UpdateRoomChannelListing(
    $id: ID!
    $input: RoomChannelListingUpdateInput!
) {
    roomChannelListingUpdate(id: $id, input: $input) {
        roomChannelListingErrors {
            field
            message
            code
            channels
        }
        room {
            slug
            channelListings {
                isPublished
                publicationDate
                visibleInListings
                channel {
                    slug
                }
                purchaseCost {
                    start {
                        amount
                    }
                    stop {
                        amount
                    }
                }
                margin {
                    start
                    stop
                }
                isAvailableForPurchase
                availableForPurchase
            }
        }
    }
}
"""


def test_room_channel_listing_update_duplicated_ids_in_add_and_remove(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [{"channelId": channel_id, "isPublished": True}],
            "removeChannels": [channel_id],
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    errors = content["data"]["roomChannelListingUpdate"][
        "roomChannelListingErrors"
    ]
    assert len(errors) == 1
    assert errors[0]["field"] == "input"
    assert errors[0]["code"] == RoomErrorCode.DUPLICATED_INPUT_ITEM.name
    assert errors[0]["channels"] == [channel_id]


def test_room_channel_listing_update_duplicated_channel_in_add(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [
                {"channelId": channel_id, "isPublished": True},
                {"channelId": channel_id, "isPublished": False},
            ],
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    errors = content["data"]["roomChannelListingUpdate"][
        "roomChannelListingErrors"
    ]
    assert len(errors) == 1
    assert errors[0]["field"] == "addChannels"
    assert errors[0]["code"] == RoomErrorCode.DUPLICATED_INPUT_ITEM.name
    assert errors[0]["channels"] == [channel_id]


def test_room_channel_listing_update_duplicated_channel_in_remove(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": room_id,
        "input": {"removeChannels": [channel_id, channel_id]},
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    errors = content["data"]["roomChannelListingUpdate"][
        "roomChannelListingErrors"
    ]
    assert len(errors) == 1
    assert errors[0]["field"] == "removeChannels"
    assert errors[0]["code"] == RoomErrorCode.DUPLICATED_INPUT_ITEM.name
    assert errors[0]["channels"] == [channel_id]


def test_room_channel_listing_update_with_empty_input(
    staff_api_client, room, permission_manage_rooms
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    variables = {
        "id": room_id,
        "input": {},
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    errors = content["data"]["roomChannelListingUpdate"][
        "roomChannelListingErrors"
    ]
    assert not errors


def test_room_channel_listing_update_with_empty_lists_in_input(
    staff_api_client, room, permission_manage_rooms
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    variables = {
        "id": room_id,
        "input": {"addChannels": [], "removeChannels": []},
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    errors = content["data"]["roomChannelListingUpdate"][
        "roomChannelListingErrors"
    ]
    assert not errors


def test_room_channel_listing_update_as_staff_user(
    staff_api_client, room, permission_manage_rooms, channel_USD, channel_PLN
):
    # given
    publication_date = datetime.date.today()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    available_for_purchase_date = datetime.date(2007, 1, 1)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [
                {
                    "channelId": channel_id,
                    "isPublished": False,
                    "publicationDate": publication_date,
                    "visibleInListings": True,
                    "isAvailableForPurchase": True,
                    "availableForPurchaseDate": available_for_purchase_date,
                }
            ]
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]

    variant = room.variants.first()
    variant_channel_listing = variant.channel_listings.filter(channel_id=channel_USD.id)
    purchase_cost, margin = get_room_costs_data(
        variant_channel_listing, True, channel_USD.currency_code
    )
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is True
    assert room_data["channelListings"][0]["publicationDate"] is None
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert room_data["channelListings"][0]["visibleInListings"] is True
    assert room_data["channelListings"][0]["isAvailableForPurchase"] is True
    assert (
        room_data["channelListings"][0]["availableForPurchase"]
        == datetime.date(1999, 1, 1).isoformat()
    )
    cost_start = room_data["channelListings"][0]["purchaseCost"]["start"]["amount"]
    cost_stop = room_data["channelListings"][0]["purchaseCost"]["stop"]["amount"]

    assert purchase_cost.start.amount == cost_start
    assert purchase_cost.stop.amount == cost_stop
    assert margin[0] == room_data["channelListings"][0]["margin"]["start"]
    assert margin[1] == room_data["channelListings"][0]["margin"]["stop"]
    assert room_data["channelListings"][1]["isPublished"] is False
    assert (
        room_data["channelListings"][1]["publicationDate"]
        == publication_date.isoformat()
    )
    assert room_data["channelListings"][1]["visibleInListings"] is True
    assert room_data["channelListings"][1]["channel"]["slug"] == channel_PLN.slug
    assert room_data["channelListings"][1]["isAvailableForPurchase"] is True
    assert (
        room_data["channelListings"][1]["availableForPurchase"]
        == available_for_purchase_date.isoformat()
    )


@patch("saleor.plugins.manager.PluginsManager.room_updated")
def test_room_channel_listing_update_trigger_webhook_room_updated(
    mock_room_updated,
    staff_api_client,
    room,
    permission_manage_rooms,
    channel_USD,
    channel_PLN,
):
    # given
    publication_date = datetime.date.today()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    available_for_purchase_date = datetime.date(2007, 1, 1)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [
                {
                    "channelId": channel_id,
                    "isPublished": False,
                    "publicationDate": publication_date,
                    "visibleInListings": True,
                    "isAvailableForPurchase": True,
                    "availableForPurchaseDate": available_for_purchase_date,
                }
            ]
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    get_graphql_content(response)

    # then
    mock_room_updated.assert_called_once_with(room)


def test_room_channel_listing_update_as_app(
    app_api_client, room, permission_manage_rooms, channel_USD, channel_PLN
):
    # given
    publication_date = datetime.date.today()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    available_for_purchase_date = datetime.date(2007, 1, 1)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [
                {
                    "channelId": channel_id,
                    "isPublished": False,
                    "publicationDate": publication_date,
                    "visibleInListings": True,
                    "isAvailableForPurchase": True,
                    "availableForPurchaseDate": available_for_purchase_date,
                }
            ]
        },
    }

    # when
    response = app_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is True
    assert room_data["channelListings"][0]["publicationDate"] is None
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert room_data["channelListings"][0]["visibleInListings"] is True
    assert room_data["channelListings"][0]["isAvailableForPurchase"] is True
    assert (
        room_data["channelListings"][0]["availableForPurchase"]
        == datetime.date(1999, 1, 1).isoformat()
    )
    assert room_data["channelListings"][1]["isPublished"] is False
    assert (
        room_data["channelListings"][1]["publicationDate"]
        == publication_date.isoformat()
    )
    assert room_data["channelListings"][1]["visibleInListings"] is True
    assert room_data["channelListings"][1]["channel"]["slug"] == channel_PLN.slug
    assert room_data["channelListings"][1]["isAvailableForPurchase"] is True
    assert (
        room_data["channelListings"][1]["availableForPurchase"]
        == available_for_purchase_date.isoformat()
    )


def test_room_channel_listing_update_as_customer(
    user_api_client, room, channel_PLN
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    variables = {
        "id": room_id,
        "input": {"addChannels": [{"channelId": channel_id, "isPublished": False}]},
    }

    # when
    response = user_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION, variables=variables
    )

    # then
    assert_no_permission(response)


def test_room_channel_listing_update_as_anonymous(api_client, room, channel_PLN):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    variables = {
        "id": room_id,
        "input": {"addChannels": [{"channelId": channel_id, "isPublished": False}]},
    }

    # when
    response = api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION, variables=variables
    )

    # then
    assert_no_permission(response)


def test_room_channel_listing_update_add_channel(
    staff_api_client, room, permission_manage_rooms, channel_USD, channel_PLN
):
    # given
    publication_date = datetime.date.today()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    available_for_purchase_date = datetime.date(2007, 1, 1)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [
                {
                    "channelId": channel_id,
                    "isPublished": False,
                    "publicationDate": publication_date,
                    "visibleInListings": True,
                    "isAvailableForPurchase": True,
                    "availableForPurchaseDate": available_for_purchase_date,
                }
            ]
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is True
    assert room_data["channelListings"][0]["publicationDate"] is None
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert room_data["channelListings"][1]["isPublished"] is False
    assert (
        room_data["channelListings"][1]["publicationDate"]
        == publication_date.isoformat()
    )
    assert room_data["channelListings"][1]["channel"]["slug"] == channel_PLN.slug
    assert room_data["channelListings"][1]["visibleInListings"] is True
    assert room_data["channelListings"][1]["isAvailableForPurchase"] is True
    assert (
        room_data["channelListings"][1]["availableForPurchase"]
        == available_for_purchase_date.isoformat()
    )


@freeze_time("2020-03-18 12:00:00")
def test_room_channel_listing_update_add_channel_without_publication_date(
    staff_api_client, room, permission_manage_rooms, channel_USD, channel_PLN
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    variables = {
        "id": room_id,
        "input": {"addChannels": [{"channelId": channel_id, "isPublished": True}]},
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is True
    assert room_data["channelListings"][0]["publicationDate"] is None
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert room_data["channelListings"][1]["isPublished"] is True
    assert (
        room_data["channelListings"][1]["publicationDate"]
        == datetime.date(2020, 3, 18).isoformat()
    )
    assert room_data["channelListings"][1]["channel"]["slug"] == channel_PLN.slug


def test_room_channel_listing_update_unpublished(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    room.channel_listings.update(publication_date=datetime.date.today())
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": room_id,
        "input": {"addChannels": [{"channelId": channel_id, "isPublished": False}]},
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is False
    assert (
        room_data["channelListings"][0]["publicationDate"]
        == datetime.date.today().isoformat()
    )
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert room_data["channelListings"][0]["visibleInListings"] is True
    assert room_data["channelListings"][0]["isAvailableForPurchase"] is True
    assert (
        room_data["channelListings"][0]["availableForPurchase"]
        == datetime.date(1999, 1, 1).isoformat()
    )


@freeze_time("2020-03-18 12:00:00")
def test_room_channel_listing_update_publish_without_publication_date(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    room.channel_listings.update(is_published=False)
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": room_id,
        "input": {"addChannels": [{"channelId": channel_id, "isPublished": True}]},
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is True
    assert (
        room_data["channelListings"][0]["publicationDate"]
        == datetime.date(2020, 3, 18).isoformat()
    )
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug


def test_room_channel_listing_update_remove_publication_date(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    room.channel_listings.update(publication_date=datetime.date.today())
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": room_id,
        "input": {"addChannels": [{"channelId": channel_id, "publicationDate": None}]},
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is True
    assert room_data["channelListings"][0]["publicationDate"] is None
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert room_data["channelListings"][0]["visibleInListings"] is True
    assert room_data["channelListings"][0]["isAvailableForPurchase"] is True
    assert (
        room_data["channelListings"][0]["availableForPurchase"]
        == datetime.date(1999, 1, 1).isoformat()
    )


def test_room_channel_listing_update_visible_in_listings(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [{"channelId": channel_id, "visibleInListings": False}]
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is True
    assert room_data["channelListings"][0]["publicationDate"] is None
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert room_data["channelListings"][0]["visibleInListings"] is False
    assert room_data["channelListings"][0]["isAvailableForPurchase"] is True
    assert (
        room_data["channelListings"][0]["availableForPurchase"]
        == datetime.date(1999, 1, 1).isoformat()
    )


def test_room_channel_listing_update_update_publication_data(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    publication_date = datetime.date.today()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [
                {
                    "channelId": channel_id,
                    "isPublished": False,
                    "publicationDate": publication_date,
                }
            ]
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is False
    assert (
        room_data["channelListings"][0]["publicationDate"]
        == publication_date.isoformat()
    )
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert room_data["channelListings"][0]["visibleInListings"] is True
    assert room_data["channelListings"][0]["isAvailableForPurchase"] is True
    assert (
        room_data["channelListings"][0]["availableForPurchase"]
        == datetime.date(1999, 1, 1).isoformat()
    )


def test_room_channel_listing_update_update_is_available_for_purchase_false(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [{"channelId": channel_id, "isAvailableForPurchase": False}]
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is True
    assert not room_data["channelListings"][0]["publicationDate"]
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert room_data["channelListings"][0]["visibleInListings"] is True
    assert room_data["channelListings"][0]["isAvailableForPurchase"] is False
    assert not room_data["channelListings"][0]["availableForPurchase"]


def test_room_channel_listing_update_update_is_available_for_purchase_without_date(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [{"channelId": channel_id, "isAvailableForPurchase": True}]
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is True
    assert not room_data["channelListings"][0]["publicationDate"]
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert room_data["channelListings"][0]["visibleInListings"] is True
    assert room_data["channelListings"][0]["isAvailableForPurchase"] is True
    assert (
        room_data["channelListings"][0]["availableForPurchase"]
        == datetime.date.today().isoformat()
    )


def test_room_channel_listing_update_update_is_available_for_purchase_past_date(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    available_for_purchase_date = datetime.date(2007, 1, 1)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [
                {
                    "channelId": channel_id,
                    "isAvailableForPurchase": True,
                    "availableForPurchaseDate": available_for_purchase_date,
                }
            ]
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is True
    assert not room_data["channelListings"][0]["publicationDate"]
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert room_data["channelListings"][0]["visibleInListings"] is True
    assert room_data["channelListings"][0]["isAvailableForPurchase"] is True
    assert (
        room_data["channelListings"][0]["availableForPurchase"]
        == available_for_purchase_date.isoformat()
    )


def test_room_channel_listing_update_update_is_available_for_purchase_future_date(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    available_for_purchase_date = datetime.date.today() + datetime.timedelta(days=1)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [
                {
                    "channelId": channel_id,
                    "isAvailableForPurchase": True,
                    "availableForPurchaseDate": available_for_purchase_date,
                }
            ]
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is True
    assert not room_data["channelListings"][0]["publicationDate"]
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug
    assert room_data["channelListings"][0]["visibleInListings"] is True
    assert room_data["channelListings"][0]["isAvailableForPurchase"] is False
    assert (
        room_data["channelListings"][0]["availableForPurchase"]
        == available_for_purchase_date.isoformat()
    )


def test_room_channel_listing_update_update_is_available_for_purchase_false_and_date(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    available_for_purchase_date = datetime.date.today() + datetime.timedelta(days=1)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [
                {
                    "channelId": channel_id,
                    "isAvailableForPurchase": False,
                    "availableForPurchaseDate": available_for_purchase_date,
                }
            ]
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    errors = data["roomChannelListingErrors"]
    assert errors[0]["field"] == "availableForPurchaseDate"
    assert errors[0]["code"] == RoomErrorCode.INVALID.name
    assert errors[0]["channels"] == [channel_id]
    assert len(errors) == 1


def test_room_channel_listing_update_remove_channel(
    staff_api_client,
    room_available_in_many_channels,
    permission_manage_rooms,
    channel_USD,
    channel_PLN,
):
    # given
    room = room_available_in_many_channels
    room_channel_listing_pln = room.channel_listings.get(channel=channel_PLN)
    variant = room.variants.get()
    variant_channel_listing_pln = variant.channel_listings.get(channel=channel_PLN)
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {
        "id": room_id,
        "input": {"removeChannels": [channel_id]},
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert len(room_data["channelListings"]) == 1
    assert room.channel_listings.get() == room_channel_listing_pln
    assert variant.channel_listings.get() == variant_channel_listing_pln


def test_room_channel_listing_update_remove_not_assigned_channel(
    staff_api_client, room, permission_manage_rooms, channel_USD, channel_PLN
):
    # given
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    variables = {
        "id": room_id,
        "input": {"removeChannels": [channel_id]},
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    room_data = data["room"]
    assert not data["roomChannelListingErrors"]
    assert room_data["slug"] == room.slug
    assert room_data["channelListings"][0]["isPublished"] is True
    assert room_data["channelListings"][0]["publicationDate"] is None
    assert room_data["channelListings"][0]["channel"]["slug"] == channel_USD.slug


def test_room_channel_listing_update_publish_room_without_category(
    staff_api_client, room, permission_manage_rooms, channel_USD, channel_PLN
):
    # given
    room.channel_listings.all().delete()
    room.category = None
    room.save()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    channel_usd_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    channel_pln_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    variables = {
        "id": room_id,
        "input": {
            "addChannels": [
                {"channelId": channel_usd_id, "isPublished": True},
                {"channelId": channel_pln_id, "isPublished": False},
            ]
        },
    }

    # when
    response = staff_api_client.post_graphql(
        ROOM_CHANNEL_LISTING_UPDATE_MUTATION,
        variables=variables,
        permissions=(permission_manage_rooms,),
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomChannelListingUpdate"]
    errors = data["roomChannelListingErrors"]
    assert errors[0]["field"] == "isPublished"
    assert errors[0]["code"] == RoomErrorCode.ROOM_WITHOUT_CATEGORY.name
    assert errors[0]["channels"] == [channel_usd_id]
    assert len(errors) == 1
