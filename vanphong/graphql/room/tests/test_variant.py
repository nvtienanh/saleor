from unittest.mock import ANY, patch
from uuid import uuid4

import graphene
import pytest
from django.utils.text import slugify
from measurement.measures import Weight
from prices import Money, TaxedMoney

from ....attribute import AttributeInputType
from ....attribute.utils import associate_attribute_values_to_instance
from ....core.weight import WeightUnits
from ....order import OrderStatus
from ....order.models import OrderLine
from ....room.error_codes import RoomErrorCode
from ....room.models import Room, RoomChannelListing, RoomVariant
from ....hotel.error_codes import StockErrorCode
from ....hotel.models import Stock, Hotel
from ...core.enums import WeightUnitsEnum
from ...tests.utils import assert_no_permission, get_graphql_content


def test_fetch_variant(
    staff_api_client,
    room,
    permission_manage_rooms,
    site_settings,
    channel_USD,
):
    query = """
    query RoomVariantDetails($id: ID!, $countyCode: CountryCode, $channel: String) {
        roomVariant(id: $id, channel: $channel) {
            id
            stocks(countryCode: $countyCode) {
                id
            }
            attributes {
                attribute {
                    id
                    name
                    slug
                    values {
                        id
                        name
                        slug
                    }
                }
                values {
                    id
                    name
                    slug
                }
            }
            costPrice {
                currency
                amount
            }
            images {
                id
            }
            name
            channelListings {
                channel {
                    slug
                }
                price {
                    currency
                    amount
                }
                costPrice {
                    currency
                    amount
                }
            }
            room {
                id
            }
            weight {
                unit
                value
            }
        }
    }
    """
    # given
    variant = room.variants.first()
    variant.weight = Weight(kg=10)
    variant.save(update_fields=["weight"])

    site_settings.default_weight_unit = WeightUnits.GRAM
    site_settings.save(update_fields=["default_weight_unit"])

    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id, "countyCode": "EU", "channel": channel_USD.slug}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)

    # when
    response = staff_api_client.post_graphql(query, variables)

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["name"] == variant.name
    assert len(data["stocks"]) == variant.stocks.count()
    assert data["weight"]["value"] == 10000
    assert data["weight"]["unit"] == WeightUnitsEnum.G.name
    channel_listing_data = data["channelListings"][0]
    channel_listing = variant.channel_listings.get()
    assert channel_listing_data["channel"]["slug"] == channel_listing.channel.slug
    assert channel_listing_data["price"]["currency"] == channel_listing.currency
    assert channel_listing_data["price"]["amount"] == channel_listing.price_amount
    assert channel_listing_data["costPrice"]["currency"] == channel_listing.currency
    assert (
        channel_listing_data["costPrice"]["amount"] == channel_listing.cost_price_amount
    )


QUERY_ROOM_VARIANT_CHANNEL_LISTING = """
    query RoomVariantDetails($id: ID!, $channel: String) {
        roomVariant(id: $id, channel: $channel) {
            id
            channelListings {
                channel {
                    slug
                }
                price {
                    currency
                    amount
                }
                costPrice {
                    currency
                    amount
                }
            }
        }
    }
"""


def test_get_room_variant_channel_listing_as_staff_user(
    staff_api_client,
    room_available_in_many_channels,
    permission_manage_rooms,
    channel_USD,
):
    # given
    variant = room_available_in_many_channels.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id, "channel": channel_USD.slug}

    # when
    response = staff_api_client.post_graphql(
        QUERY_ROOM_VARIANT_CHANNEL_LISTING,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomVariant"]
    channel_listings = variant.channel_listings.all()
    for channel_listing in channel_listings:
        assert {
            "channel": {"slug": channel_listing.channel.slug},
            "price": {
                "currency": channel_listing.currency,
                "amount": channel_listing.price_amount,
            },
            "costPrice": {
                "currency": channel_listing.currency,
                "amount": channel_listing.cost_price_amount,
            },
        } in data["channelListings"]
    assert len(data["channelListings"]) == variant.channel_listings.count()


def test_get_room_variant_channel_listing_as_app(
    app_api_client,
    room_available_in_many_channels,
    permission_manage_rooms,
    channel_USD,
):
    # given
    variant = room_available_in_many_channels.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id, "channel": channel_USD.slug}

    # when
    response = app_api_client.post_graphql(
        QUERY_ROOM_VARIANT_CHANNEL_LISTING,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["roomVariant"]
    channel_listings = variant.channel_listings.all()
    for channel_listing in channel_listings:
        assert {
            "channel": {"slug": channel_listing.channel.slug},
            "price": {
                "currency": channel_listing.currency,
                "amount": channel_listing.price_amount,
            },
            "costPrice": {
                "currency": channel_listing.currency,
                "amount": channel_listing.cost_price_amount,
            },
        } in data["channelListings"]
    assert len(data["channelListings"]) == variant.channel_listings.count()


def test_get_room_variant_channel_listing_as_customer(
    user_api_client,
    room_available_in_many_channels,
    channel_USD,
):
    # given
    variant = room_available_in_many_channels.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id, "channel": channel_USD.slug}

    # when
    response = user_api_client.post_graphql(
        QUERY_ROOM_VARIANT_CHANNEL_LISTING,
        variables,
    )

    # then
    assert_no_permission(response)


def test_get_room_variant_channel_listing_as_anonymous(
    api_client,
    room_available_in_many_channels,
    channel_USD,
):
    # given
    variant = room_available_in_many_channels.variants.get()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id, "channel": channel_USD.slug}

    # when
    response = api_client.post_graphql(
        QUERY_ROOM_VARIANT_CHANNEL_LISTING,
        variables,
    )

    # then
    assert_no_permission(response)


CREATE_VARIANT_MUTATION = """
      mutation createVariant (
            $roomId: ID!,
            $sku: String,
            $stocks: [StockInput!],
            $attributes: [AttributeValueInput]!,
            $weight: WeightScalar,
            $trackInventory: Boolean) {
                roomVariantCreate(
                    input: {
                        room: $roomId,
                        sku: $sku,
                        stocks: $stocks,
                        attributes: $attributes,
                        trackInventory: $trackInventory,
                        weight: $weight
                    }) {
                    roomErrors {
                      field
                      message
                      attributes
                      code
                    }
                    roomVariant {
                        name
                        sku
                        attributes {
                            attribute {
                                slug
                            }
                            values {
                                name
                                slug
                                file {
                                    url
                                    contentType
                                }
                            }
                        }
                        costPrice {
                            currency
                            amount
                            localized
                        }
                        weight {
                            value
                            unit
                        }
                        stocks {
                            quantity
                            hotel {
                                slug
                            }
                        }
                    }
                }
            }

"""


@patch("vanphong.plugins.manager.PluginsManager.room_updated")
def test_create_variant(
    updated_webhook_mock,
    staff_api_client,
    room,
    room_type,
    permission_manage_rooms,
    hotel,
):
    query = CREATE_VARIANT_MUTATION
    room_id = graphene.Node.to_global_id("Room", room.pk)
    sku = "1"
    weight = 10.22
    variant_slug = room_type.variant_attributes.first().slug
    variant_id = graphene.Node.to_global_id(
        "Attribute", room_type.variant_attributes.first().pk
    )
    variant_value = "test-value"
    stocks = [
        {
            "hotel": graphene.Node.to_global_id("Hotel", hotel.pk),
            "quantity": 20,
        }
    ]

    variables = {
        "roomId": room_id,
        "sku": sku,
        "stocks": stocks,
        "weight": weight,
        "attributes": [{"id": variant_id, "values": [variant_value]}],
        "trackInventory": True,
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)["data"]["roomVariantCreate"]
    assert not content["roomErrors"]
    data = content["roomVariant"]
    assert data["name"] == variant_value
    assert data["sku"] == sku
    assert data["attributes"][0]["attribute"]["slug"] == variant_slug
    assert data["attributes"][0]["values"][0]["slug"] == variant_value
    assert data["weight"]["unit"] == WeightUnitsEnum.KG.name
    assert data["weight"]["value"] == weight
    assert len(data["stocks"]) == 1
    assert data["stocks"][0]["quantity"] == stocks[0]["quantity"]
    assert data["stocks"][0]["hotel"]["slug"] == hotel.slug
    updated_webhook_mock.assert_called_once_with(room)


@patch("vanphong.plugins.manager.PluginsManager.room_updated")
def test_create_variant_with_file_attribute(
    updated_webhook_mock,
    staff_api_client,
    room,
    room_type,
    file_attribute,
    permission_manage_rooms,
    hotel,
):
    query = CREATE_VARIANT_MUTATION
    room_id = graphene.Node.to_global_id("Room", room.pk)
    sku = "1"
    weight = 10.22

    room_type.variant_attributes.clear()
    room_type.variant_attributes.add(file_attribute)
    file_attr_id = graphene.Node.to_global_id("Attribute", file_attribute.id)
    existing_value = file_attribute.values.first()

    values_count = file_attribute.values.count()

    stocks = [
        {
            "hotel": graphene.Node.to_global_id("Hotel", hotel.pk),
            "quantity": 20,
        }
    ]

    variables = {
        "roomId": room_id,
        "sku": sku,
        "stocks": stocks,
        "weight": weight,
        "attributes": [{"id": file_attr_id, "file": existing_value.file_url}],
        "trackInventory": True,
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)["data"]["roomVariantCreate"]
    assert not content["roomErrors"]
    data = content["roomVariant"]
    assert data["name"] == sku
    assert data["sku"] == sku
    assert data["attributes"][0]["attribute"]["slug"] == file_attribute.slug
    assert data["attributes"][0]["values"][0]["slug"] == f"{existing_value.slug}-2"
    assert data["attributes"][0]["values"][0]["name"] == existing_value.name
    assert data["weight"]["unit"] == WeightUnitsEnum.KG.name
    assert data["weight"]["value"] == weight
    assert len(data["stocks"]) == 1
    assert data["stocks"][0]["quantity"] == stocks[0]["quantity"]
    assert data["stocks"][0]["hotel"]["slug"] == hotel.slug

    file_attribute.refresh_from_db()
    assert file_attribute.values.count() == values_count + 1

    updated_webhook_mock.assert_called_once_with(room)


@patch("vanphong.plugins.manager.PluginsManager.room_updated")
def test_create_variant_with_file_attribute_new_value(
    updated_webhook_mock,
    staff_api_client,
    room,
    room_type,
    file_attribute,
    permission_manage_rooms,
    hotel,
):
    query = CREATE_VARIANT_MUTATION
    room_id = graphene.Node.to_global_id("Room", room.pk)
    sku = "1"
    price = 1.32
    cost_price = 3.22
    weight = 10.22

    room_type.variant_attributes.clear()
    room_type.variant_attributes.add(file_attribute)
    file_attr_id = graphene.Node.to_global_id("Attribute", file_attribute.id)
    new_value = "new_value.txt"

    values_count = file_attribute.values.count()

    stocks = [
        {
            "hotel": graphene.Node.to_global_id("Hotel", hotel.pk),
            "quantity": 20,
        }
    ]

    variables = {
        "roomId": room_id,
        "sku": sku,
        "stocks": stocks,
        "costPrice": cost_price,
        "price": price,
        "weight": weight,
        "attributes": [{"id": file_attr_id, "file": new_value}],
        "trackInventory": True,
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)["data"]["roomVariantCreate"]
    assert not content["roomErrors"]
    data = content["roomVariant"]
    assert data["name"] == sku
    assert data["sku"] == sku
    assert data["attributes"][0]["attribute"]["slug"] == file_attribute.slug
    assert data["attributes"][0]["values"][0]["slug"] == slugify(new_value)
    assert data["weight"]["unit"] == WeightUnitsEnum.KG.name
    assert data["weight"]["value"] == weight
    assert len(data["stocks"]) == 1
    assert data["stocks"][0]["quantity"] == stocks[0]["quantity"]
    assert data["stocks"][0]["hotel"]["slug"] == hotel.slug

    file_attribute.refresh_from_db()
    assert file_attribute.values.count() == values_count + 1

    updated_webhook_mock.assert_called_once_with(room)


@patch("vanphong.plugins.manager.PluginsManager.room_updated")
def test_create_variant_with_file_attribute_no_file_url_given(
    updated_webhook_mock,
    staff_api_client,
    room,
    room_type,
    file_attribute,
    permission_manage_rooms,
    hotel,
):
    query = CREATE_VARIANT_MUTATION
    room_id = graphene.Node.to_global_id("Room", room.pk)
    sku = "1"
    price = 1.32
    cost_price = 3.22
    weight = 10.22

    room_type.variant_attributes.clear()
    room_type.variant_attributes.add(file_attribute)
    file_attr_id = graphene.Node.to_global_id("Attribute", file_attribute.id)

    values_count = file_attribute.values.count()

    stocks = [
        {
            "hotel": graphene.Node.to_global_id("Hotel", hotel.pk),
            "quantity": 20,
        }
    ]

    variables = {
        "roomId": room_id,
        "sku": sku,
        "stocks": stocks,
        "costPrice": cost_price,
        "price": price,
        "weight": weight,
        "attributes": [{"id": file_attr_id}],
        "trackInventory": True,
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)["data"]["roomVariantCreate"]
    errors = content["roomErrors"]
    data = content["roomVariant"]
    assert not errors
    assert data["name"] == sku
    assert data["sku"] == sku
    assert data["attributes"][0]["attribute"]["slug"] == file_attribute.slug
    assert len(data["attributes"][0]["values"]) == 0
    assert data["weight"]["unit"] == WeightUnitsEnum.KG.name
    assert data["weight"]["value"] == weight
    assert len(data["stocks"]) == 1
    assert data["stocks"][0]["quantity"] == stocks[0]["quantity"]
    assert data["stocks"][0]["hotel"]["slug"] == hotel.slug

    file_attribute.refresh_from_db()
    assert file_attribute.values.count() == values_count

    updated_webhook_mock.assert_called_once_with(room)


def test_create_room_variant_with_negative_weight(
    staff_api_client, room, room_type, permission_manage_rooms
):
    query = CREATE_VARIANT_MUTATION
    room_id = graphene.Node.to_global_id("Room", room.pk)

    variant_id = graphene.Node.to_global_id(
        "Attribute", room_type.variant_attributes.first().pk
    )
    variant_value = "test-value"

    variables = {
        "roomId": room_id,
        "weight": -1,
        "attributes": [{"id": variant_id, "values": [variant_value]}],
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantCreate"]
    error = data["roomErrors"][0]
    assert error["field"] == "weight"
    assert error["code"] == RoomErrorCode.INVALID.name


def test_create_room_variant_without_attributes(
    staff_api_client, room, permission_manage_rooms
):
    # given
    query = CREATE_VARIANT_MUTATION
    room_id = graphene.Node.to_global_id("Room", room.pk)
    variables = {
        "roomId": room_id,
        "sku": "test-sku",
        "price": 0,
        "attributes": [],
    }

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariantCreate"]
    error = data["roomErrors"][0]

    assert error["field"] == "attributes"
    assert error["code"] == RoomErrorCode.REQUIRED.name


def test_create_room_variant_not_all_attributes(
    staff_api_client, room, room_type, color_attribute, permission_manage_rooms
):
    query = CREATE_VARIANT_MUTATION
    room_id = graphene.Node.to_global_id("Room", room.pk)
    sku = "1"
    variant_id = graphene.Node.to_global_id(
        "Attribute", room_type.variant_attributes.first().pk
    )
    variant_value = "test-value"
    room_type.variant_attributes.add(color_attribute)

    variables = {
        "roomId": room_id,
        "sku": sku,
        "attributes": [{"id": variant_id, "values": [variant_value]}],
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    assert content["data"]["roomVariantCreate"]["roomErrors"]
    assert content["data"]["roomVariantCreate"]["roomErrors"][0] == {
        "field": "attributes",
        "code": RoomErrorCode.REQUIRED.name,
        "message": ANY,
        "attributes": None,
    }
    assert not room.variants.filter(sku=sku).exists()


def test_create_room_variant_duplicated_attributes(
    staff_api_client,
    room_with_variant_with_two_attributes,
    color_attribute,
    size_attribute,
    permission_manage_rooms,
):
    query = CREATE_VARIANT_MUTATION
    room = room_with_variant_with_two_attributes
    room_id = graphene.Node.to_global_id("Room", room.pk)
    color_attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.id)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.id)
    sku = str(uuid4())[:12]
    variables = {
        "roomId": room_id,
        "sku": sku,
        "attributes": [
            {"id": color_attribute_id, "values": ["red"]},
            {"id": size_attribute_id, "values": ["small"]},
        ],
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    assert content["data"]["roomVariantCreate"]["roomErrors"]
    assert content["data"]["roomVariantCreate"]["roomErrors"][0] == {
        "field": "attributes",
        "code": RoomErrorCode.DUPLICATED_INPUT_ITEM.name,
        "message": ANY,
        "attributes": None,
    }
    assert not room.variants.filter(sku=sku).exists()


def test_create_variant_invalid_variant_attributes(
    staff_api_client,
    room,
    room_type,
    permission_manage_rooms,
    hotel,
    color_attribute,
    weight_attribute,
):
    query = CREATE_VARIANT_MUTATION
    room_id = graphene.Node.to_global_id("Room", room.pk)
    sku = "1"
    price = 1.32
    cost_price = 3.22
    weight = 10.22

    # Default attribute defined in room_type fixture
    size_attribute = room_type.variant_attributes.get(name="Size")
    size_value_slug = size_attribute.values.first().slug
    size_attr_id = graphene.Node.to_global_id("Attribute", size_attribute.id)

    # Add second attribute
    room_type.variant_attributes.add(color_attribute)
    color_attr_id = graphene.Node.to_global_id("Attribute", color_attribute.id)
    non_existent_attr_value = "The cake is a lie"

    # Add third attribute
    room_type.variant_attributes.add(weight_attribute)
    weight_attr_id = graphene.Node.to_global_id("Attribute", weight_attribute.id)

    stocks = [
        {
            "hotel": graphene.Node.to_global_id("Hotel", hotel.pk),
            "quantity": 20,
        }
    ]

    variables = {
        "roomId": room_id,
        "sku": sku,
        "stocks": stocks,
        "costPrice": cost_price,
        "price": price,
        "weight": weight,
        "attributes": [
            {"id": color_attr_id, "values": [" "]},
            {"id": weight_attr_id, "values": [None]},
            {"id": size_attr_id, "values": [non_existent_attr_value, size_value_slug]},
        ],
        "trackInventory": True,
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)

    data = content["data"]["roomVariantCreate"]
    errors = data["roomErrors"]

    assert not data["roomVariant"]
    assert len(errors) == 2

    expected_errors = [
        {
            "attributes": [color_attr_id, weight_attr_id],
            "code": RoomErrorCode.REQUIRED.name,
            "field": "attributes",
            "message": ANY,
        },
        {
            "attributes": [size_attr_id],
            "code": RoomErrorCode.INVALID.name,
            "field": "attributes",
            "message": ANY,
        },
    ]
    for error in expected_errors:
        assert error in errors


def test_create_room_variant_update_with_new_attributes(
    staff_api_client, permission_manage_rooms, room, size_attribute
):
    query = """
        mutation VariantUpdate(
          $id: ID!
          $attributes: [AttributeValueInput]
          $sku: String
          $trackInventory: Boolean!
        ) {
          roomVariantUpdate(
            id: $id
            input: {
              attributes: $attributes
              sku: $sku
              trackInventory: $trackInventory
            }
          ) {
            errors {
              field
              message
            }
            roomVariant {
              id
              attributes {
                attribute {
                  id
                  name
                  slug
                  values {
                    id
                    name
                    slug
                    __typename
                  }
                  __typename
                }
                __typename
              }
            }
          }
        }
    """

    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    variant_id = graphene.Node.to_global_id(
        "RoomVariant", room.variants.first().pk
    )

    variables = {
        "attributes": [{"id": size_attribute_id, "values": ["XXXL"]}],
        "id": variant_id,
        "sku": "21599567",
        "trackInventory": True,
    }

    data = get_graphql_content(
        staff_api_client.post_graphql(
            query, variables, permissions=[permission_manage_rooms]
        )
    )["data"]["roomVariantUpdate"]
    assert not data["errors"]
    assert data["roomVariant"]["id"] == variant_id

    attributes = data["roomVariant"]["attributes"]
    assert len(attributes) == 1
    assert attributes[0]["attribute"]["id"] == size_attribute_id


@patch("vanphong.plugins.manager.PluginsManager.room_updated")
def test_update_room_variant(
    updated_webhook_mock,
    staff_api_client,
    room,
    size_attribute,
    permission_manage_rooms,
):
    query = """
        mutation updateVariant (
            $id: ID!,
            $sku: String!,
            $trackInventory: Boolean!,
            $attributes: [AttributeValueInput]) {
                roomVariantUpdate(
                    id: $id,
                    input: {
                        sku: $sku,
                        trackInventory: $trackInventory,
                        attributes: $attributes,
                    }) {
                    roomVariant {
                        name
                        sku
                        channelListings {
                            channel {
                                slug
                            }
                        }
                        costPrice {
                            currency
                            amount
                            localized
                        }
                    }
                }
            }

    """
    variant = room.variants.first()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    sku = "test sku"

    variables = {
        "id": variant_id,
        "sku": sku,
        "trackInventory": True,
        "attributes": [{"id": attribute_id, "values": ["S"]}],
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    variant.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["roomVariantUpdate"]["roomVariant"]
    assert data["name"] == variant.name
    assert data["sku"] == sku
    updated_webhook_mock.assert_called_once_with(room)


def test_update_room_variant_with_negative_weight(
    staff_api_client, room, permission_manage_rooms
):
    query = """
        mutation updateVariant (
            $id: ID!,
            $weight: WeightScalar
        ) {
            roomVariantUpdate(
                id: $id,
                input: {
                    weight: $weight,
                }
            ){
                roomVariant {
                    name
                }
                roomErrors {
                    field
                    message
                    code
                }
            }
        }
    """
    variant = room.variants.first()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id, "weight": -1}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    variant.refresh_from_db()
    content = get_graphql_content(response)
    data = content["data"]["roomVariantUpdate"]
    error = data["roomErrors"][0]
    assert error["field"] == "weight"
    assert error["code"] == RoomErrorCode.INVALID.name


QUERY_UPDATE_VARIANT_ATTRIBUTES = """
    mutation updateVariant (
        $id: ID!,
        $sku: String,
        $attributes: [AttributeValueInput]!) {
            roomVariantUpdate(
                id: $id,
                input: {
                    sku: $sku,
                    attributes: $attributes
                }) {
                roomVariant {
                    sku
                    attributes {
                        attribute {
                            slug
                        }
                        values {
                            slug
                            name
                            file {
                                url
                                contentType
                            }
                        }
                    }
                }
                errors {
                    field
                    message
                }
                roomErrors {
                    field
                    code
                }
            }
        }
"""


def test_update_room_variant_not_all_attributes(
    staff_api_client, room, room_type, color_attribute, permission_manage_rooms
):
    """Ensures updating a variant with missing attributes (all attributes must
    be provided) raises an error. We expect the color attribute
    to be flagged as missing."""

    query = QUERY_UPDATE_VARIANT_ATTRIBUTES
    variant = room.variants.first()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    sku = "test sku"
    attr_id = graphene.Node.to_global_id(
        "Attribute", room_type.variant_attributes.first().id
    )
    variant_value = "test-value"
    room_type.variant_attributes.add(color_attribute)

    variables = {
        "id": variant_id,
        "sku": sku,
        "attributes": [{"id": attr_id, "values": [variant_value]}],
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    variant.refresh_from_db()
    content = get_graphql_content(response)
    assert len(content["data"]["roomVariantUpdate"]["errors"]) == 1
    assert content["data"]["roomVariantUpdate"]["errors"][0] == {
        "field": "attributes",
        "message": "All variant selection attributes must take a value.",
    }
    assert not room.variants.filter(sku=sku).exists()


def test_update_room_variant_with_current_attribute(
    staff_api_client,
    room_with_variant_with_two_attributes,
    color_attribute,
    size_attribute,
    permission_manage_rooms,
):
    room = room_with_variant_with_two_attributes
    variant = room.variants.first()
    sku = str(uuid4())[:12]
    assert not variant.sku == sku
    assert variant.attributes.first().values.first().slug == "red"
    assert variant.attributes.last().values.first().slug == "small"

    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    color_attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.pk)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)

    variables = {
        "id": variant_id,
        "sku": sku,
        "attributes": [
            {"id": color_attribute_id, "values": ["red"]},
            {"id": size_attribute_id, "values": ["small"]},
        ],
    }

    response = staff_api_client.post_graphql(
        QUERY_UPDATE_VARIANT_ATTRIBUTES,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)

    data = content["data"]["roomVariantUpdate"]
    assert not data["errors"]
    variant.refresh_from_db()
    assert variant.sku == sku
    assert variant.attributes.first().values.first().slug == "red"
    assert variant.attributes.last().values.first().slug == "small"


def test_update_room_variant_with_new_attribute(
    staff_api_client,
    room_with_variant_with_two_attributes,
    color_attribute,
    size_attribute,
    permission_manage_rooms,
):
    room = room_with_variant_with_two_attributes
    variant = room.variants.first()
    sku = str(uuid4())[:12]
    assert not variant.sku == sku
    assert variant.attributes.first().values.first().slug == "red"
    assert variant.attributes.last().values.first().slug == "small"

    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    color_attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.pk)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)

    variables = {
        "id": variant_id,
        "sku": sku,
        "attributes": [
            {"id": color_attribute_id, "values": ["red"]},
            {"id": size_attribute_id, "values": ["big"]},
        ],
    }

    response = staff_api_client.post_graphql(
        QUERY_UPDATE_VARIANT_ATTRIBUTES,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)

    data = content["data"]["roomVariantUpdate"]
    assert not data["errors"]
    variant.refresh_from_db()
    assert variant.sku == sku
    assert variant.attributes.first().values.first().slug == "red"
    assert variant.attributes.last().values.first().slug == "big"


def test_update_room_variant_with_duplicated_attribute(
    staff_api_client,
    room_with_variant_with_two_attributes,
    color_attribute,
    size_attribute,
    permission_manage_rooms,
):
    room = room_with_variant_with_two_attributes
    variant = room.variants.first()
    variant2 = room.variants.first()

    variant2.pk = None
    variant2.sku = str(uuid4())[:12]
    variant2.save()
    associate_attribute_values_to_instance(
        variant2, color_attribute, color_attribute.values.last()
    )
    associate_attribute_values_to_instance(
        variant2, size_attribute, size_attribute.values.last()
    )

    assert variant.attributes.first().values.first().slug == "red"
    assert variant.attributes.last().values.first().slug == "small"
    assert variant2.attributes.first().values.first().slug == "blue"
    assert variant2.attributes.last().values.first().slug == "big"

    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    color_attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.pk)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)

    variables = {
        "id": variant_id,
        "attributes": [
            {"id": color_attribute_id, "values": ["blue"]},
            {"id": size_attribute_id, "values": ["big"]},
        ],
    }

    response = staff_api_client.post_graphql(
        QUERY_UPDATE_VARIANT_ATTRIBUTES,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)

    data = content["data"]["roomVariantUpdate"]
    assert data["roomErrors"][0] == {
        "field": "attributes",
        "code": RoomErrorCode.DUPLICATED_INPUT_ITEM.name,
    }


def test_update_room_variant_with_current_file_attribute(
    staff_api_client,
    room_with_variant_with_file_attribute,
    file_attribute,
    permission_manage_rooms,
):
    room = room_with_variant_with_file_attribute
    variant = room.variants.first()
    sku = str(uuid4())[:12]
    assert not variant.sku == sku
    assert set(variant.attributes.first().values.values_list("slug", flat=True)) == {
        "test_filetxt"
    }
    second_value = file_attribute.values.last()

    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    file_attribute_id = graphene.Node.to_global_id("Attribute", file_attribute.pk)

    variables = {
        "id": variant_id,
        "sku": sku,
        "price": 15,
        "attributes": [{"id": file_attribute_id, "file": second_value.file_url}],
    }

    response = staff_api_client.post_graphql(
        QUERY_UPDATE_VARIANT_ATTRIBUTES,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)

    data = content["data"]["roomVariantUpdate"]
    assert not data["errors"]
    variant_data = data["roomVariant"]
    assert variant_data
    assert variant_data["sku"] == sku
    assert len(variant_data["attributes"]) == 1
    assert variant_data["attributes"][0]["attribute"]["slug"] == file_attribute.slug
    assert len(variant_data["attributes"][0]["values"]) == 1
    assert (
        variant_data["attributes"][0]["values"][0]["slug"]
        == f"{slugify(second_value)}-2"
    )


def test_update_room_variant_with_duplicated_file_attribute(
    staff_api_client,
    room_with_variant_with_file_attribute,
    file_attribute,
    permission_manage_rooms,
):
    room = room_with_variant_with_file_attribute
    variant = room.variants.first()
    variant2 = room.variants.first()

    variant2.pk = None
    variant2.sku = str(uuid4())[:12]
    variant2.save()
    file_attr_value = file_attribute.values.last()
    associate_attribute_values_to_instance(variant2, file_attribute, file_attr_value)

    sku = str(uuid4())[:12]
    assert not variant.sku == sku

    assert set(variant.attributes.first().values.values_list("slug", flat=True)) == {
        "test_filetxt"
    }
    assert set(variant2.attributes.first().values.values_list("slug", flat=True)) == {
        "test_filejpeg"
    }

    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    file_attribute_id = graphene.Node.to_global_id("Attribute", file_attribute.pk)

    variables = {
        "id": variant_id,
        "price": 15,
        "attributes": [{"id": file_attribute_id, "file": file_attr_value.file_url}],
        "sku": sku,
    }

    response = staff_api_client.post_graphql(
        QUERY_UPDATE_VARIANT_ATTRIBUTES,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)

    data = content["data"]["roomVariantUpdate"]
    assert data["roomErrors"][0] == {
        "field": "attributes",
        "code": RoomErrorCode.DUPLICATED_INPUT_ITEM.name,
    }


def test_update_room_variant_with_file_attribute_new_value_is_not_created(
    staff_api_client,
    room_with_variant_with_file_attribute,
    file_attribute,
    permission_manage_rooms,
):
    room = room_with_variant_with_file_attribute
    variant = room.variants.first()
    sku = str(uuid4())[:12]
    assert not variant.sku == sku

    existing_value = file_attribute.values.first()
    assert variant.attributes.filter(
        assignment__attribute=file_attribute, values=existing_value
    ).exists()

    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    file_attribute_id = graphene.Node.to_global_id("Attribute", file_attribute.pk)

    variables = {
        "id": variant_id,
        "sku": sku,
        "price": 15,
        "attributes": [{"id": file_attribute_id, "file": existing_value.file_url}],
    }

    response = staff_api_client.post_graphql(
        QUERY_UPDATE_VARIANT_ATTRIBUTES,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)

    data = content["data"]["roomVariantUpdate"]
    assert not data["errors"]
    variant_data = data["roomVariant"]
    assert variant_data
    assert variant_data["sku"] == sku
    assert len(variant_data["attributes"]) == 1
    assert variant_data["attributes"][0]["attribute"]["slug"] == file_attribute.slug
    assert len(variant_data["attributes"][0]["values"]) == 1
    value_data = variant_data["attributes"][0]["values"][0]
    assert value_data["slug"] == existing_value.slug
    assert value_data["name"] == existing_value.name
    assert value_data["file"]["url"] == existing_value.file_url
    assert value_data["file"]["contentType"] == existing_value.content_type


@pytest.mark.parametrize(
    "values, message",
    (
        ([], "Attribute expects a value but none were given"),
        (["one", "two"], "Attribute must take only one value"),
        (["   "], "Attribute values cannot be blank"),
        ([None], "Attribute values cannot be blank"),
    ),
)
def test_update_room_variant_requires_values(
    staff_api_client, variant, room_type, permission_manage_rooms, values, message
):
    """Ensures updating a variant with invalid values raise an error.

    - No values
    - Blank value
    - None as value
    - More than one value
    """

    sku = "updated"

    query = QUERY_UPDATE_VARIANT_ATTRIBUTES
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    attr_id = graphene.Node.to_global_id(
        "Attribute", room_type.variant_attributes.first().id
    )

    variables = {
        "id": variant_id,
        "attributes": [{"id": attr_id, "values": values}],
        "sku": sku,
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    variant.refresh_from_db()
    content = get_graphql_content(response)
    assert (
        len(content["data"]["roomVariantUpdate"]["errors"]) == 1
    ), f"expected: {message}"
    assert content["data"]["roomVariantUpdate"]["errors"][0] == {
        "field": "attributes",
        "message": message,
    }
    assert not variant.room.variants.filter(sku=sku).exists()


def test_update_room_variant_with_price_does_not_raise_price_validation_error(
    staff_api_client, variant, size_attribute, permission_manage_rooms
):
    mutation = """
    mutation updateVariant ($id: ID!, $attributes: [AttributeValueInput]) {
        roomVariantUpdate(
            id: $id,
            input: {
            attributes: $attributes,
        }) {
            roomVariant {
                id
            }
            roomErrors {
                field
                code
            }
        }
    }
    """
    # given a room variant and an attribute
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)

    # when running the updateVariant mutation without price input field
    variables = {
        "id": variant_id,
        "attributes": [{"id": attribute_id, "values": ["S"]}],
    }
    response = staff_api_client.post_graphql(
        mutation, variables, permissions=[permission_manage_rooms]
    )

    # then mutation passes without validation errors
    content = get_graphql_content(response)
    assert not content["data"]["roomVariantUpdate"]["roomErrors"]


DELETE_VARIANT_MUTATION = """
    mutation variantDelete($id: ID!) {
        roomVariantDelete(id: $id) {
            roomVariant {
                sku
                id
            }
            }
        }
"""


def test_delete_variant(staff_api_client, room, permission_manage_rooms):
    query = DELETE_VARIANT_MUTATION
    variant = room.variants.first()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantDelete"]
    assert data["roomVariant"]["sku"] == variant.sku
    with pytest.raises(variant._meta.model.DoesNotExist):
        variant.refresh_from_db()


def test_delete_variant_in_draft_order(
    staff_api_client,
    order_line,
    permission_manage_rooms,
    order_list,
    channel_USD,
):
    query = DELETE_VARIANT_MUTATION

    draft_order = order_line.order
    draft_order.status = OrderStatus.DRAFT
    draft_order.save(update_fields=["status"])

    variant = order_line.variant
    variant_channel_listing = variant.channel_listings.get(channel=channel_USD)
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id}

    room = variant.room
    net = variant.get_price(room, [], channel_USD, variant_channel_listing, None)
    gross = Money(amount=net.amount, currency=net.currency)
    order_not_draft = order_list[-1]
    unit_price = TaxedMoney(net=net, gross=gross)
    quantity = 3
    order_line_not_in_draft = OrderLine.objects.create(
        variant=variant,
        order=order_not_draft,
        room_name=str(room),
        variant_name=str(variant),
        room_sku=variant.sku,
        is_shipping_required=variant.is_shipping_required(),
        unit_price=unit_price,
        total_price=unit_price * quantity,
        quantity=quantity,
    )
    order_line_not_in_draft_pk = order_line_not_in_draft.pk

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    content = get_graphql_content(response)
    data = content["data"]["roomVariantDelete"]
    assert data["roomVariant"]["sku"] == variant.sku
    with pytest.raises(order_line._meta.model.DoesNotExist):
        order_line.refresh_from_db()

    assert OrderLine.objects.filter(pk=order_line_not_in_draft_pk).exists()


def test_delete_default_variant(
    staff_api_client, room_with_two_variants, permission_manage_rooms
):
    # given
    query = DELETE_VARIANT_MUTATION
    room = room_with_two_variants

    default_variant = room.variants.first()
    second_variant = room.variants.last()

    room.default_variant = default_variant
    room.save(update_fields=["default_variant"])

    assert second_variant.pk != default_variant.pk

    variant_id = graphene.Node.to_global_id("RoomVariant", default_variant.pk)
    variables = {"id": variant_id}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariantDelete"]
    assert data["roomVariant"]["sku"] == default_variant.sku
    with pytest.raises(default_variant._meta.model.DoesNotExist):
        default_variant.refresh_from_db()

    room.refresh_from_db()
    assert room.default_variant.pk == second_variant.pk


def test_delete_not_default_variant_left_default_variant_unchanged(
    staff_api_client, room_with_two_variants, permission_manage_rooms
):
    # given
    query = DELETE_VARIANT_MUTATION
    room = room_with_two_variants

    default_variant = room.variants.first()
    second_variant = room.variants.last()

    room.default_variant = default_variant
    room.save(update_fields=["default_variant"])

    assert second_variant.pk != default_variant.pk

    variant_id = graphene.Node.to_global_id("RoomVariant", second_variant.pk)
    variables = {"id": variant_id}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariantDelete"]
    assert data["roomVariant"]["sku"] == second_variant.sku
    with pytest.raises(second_variant._meta.model.DoesNotExist):
        second_variant.refresh_from_db()

    room.refresh_from_db()
    assert room.default_variant.pk == default_variant.pk


def test_delete_default_all_room_variant_left_room_default_variant_unset(
    staff_api_client, room, permission_manage_rooms
):
    # given
    query = DELETE_VARIANT_MUTATION

    default_variant = room.variants.first()

    room.default_variant = default_variant
    room.save(update_fields=["default_variant"])

    assert room.variants.count() == 1

    variant_id = graphene.Node.to_global_id("RoomVariant", default_variant.pk)
    variables = {"id": variant_id}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariantDelete"]
    assert data["roomVariant"]["sku"] == default_variant.sku
    with pytest.raises(default_variant._meta.model.DoesNotExist):
        default_variant.refresh_from_db()

    room.refresh_from_db()
    assert not room.default_variant


def _fetch_all_variants(client, variables={}, permissions=None):
    query = """
        query fetchAllVariants($channel: String) {
            roomVariants(first: 10, channel: $channel) {
                totalCount
                edges {
                    node {
                        id
                    }
                }
            }
        }
    """
    response = client.post_graphql(
        query, variables, permissions=permissions, check_no_permissions=False
    )
    content = get_graphql_content(response)
    return content["data"]["roomVariants"]


def test_fetch_all_variants_staff_user(
    staff_api_client, unavailable_room_with_variant, permission_manage_rooms
):
    variant = unavailable_room_with_variant.variants.first()
    data = _fetch_all_variants(
        staff_api_client, permissions=[permission_manage_rooms]
    )
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    assert data["totalCount"] == 1
    assert data["edges"][0]["node"]["id"] == variant_id


def test_fetch_all_variants_staff_user_with_channel(
    staff_api_client,
    room_list_with_variants_many_channel,
    permission_manage_rooms,
    channel_PLN,
):
    variables = {"channel": channel_PLN.slug}
    data = _fetch_all_variants(
        staff_api_client, variables, permissions=[permission_manage_rooms]
    )
    assert data["totalCount"] == 2


def test_fetch_all_variants_staff_user_without_channel(
    staff_api_client,
    room_list_with_variants_many_channel,
    permission_manage_rooms,
):
    data = _fetch_all_variants(
        staff_api_client, permissions=[permission_manage_rooms]
    )
    assert data["totalCount"] == 3


def test_fetch_all_variants_customer(
    user_api_client, unavailable_room_with_variant, channel_USD
):
    data = _fetch_all_variants(user_api_client, variables={"channel": channel_USD.slug})
    assert data["totalCount"] == 0


def test_fetch_all_variants_anonymous_user(
    api_client, unavailable_room_with_variant, channel_USD
):
    data = _fetch_all_variants(api_client, variables={"channel": channel_USD.slug})
    assert data["totalCount"] == 0


def test_room_variants_by_ids(user_api_client, variant, channel_USD):
    query = """
        query getRoom($ids: [ID!], $channel: String) {
            roomVariants(ids: $ids, first: 1, channel: $channel) {
                edges {
                    node {
                        id
                    }
                }
            }
        }
    """
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)

    variables = {"ids": [variant_id], "channel": channel_USD.slug}
    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["roomVariants"]
    assert data["edges"][0]["node"]["id"] == variant_id
    assert len(data["edges"]) == 1


def test_room_variants_visible_in_listings_by_customer(
    user_api_client, room_list, channel_USD
):
    # given
    room_list[0].channel_listings.all().update(visible_in_listings=False)

    room_count = Room.objects.count()

    # when
    data = _fetch_all_variants(user_api_client, variables={"channel": channel_USD.slug})

    assert data["totalCount"] == room_count - 1


def test_room_variants_visible_in_listings_by_staff_without_perm(
    staff_api_client, room_list, channel_USD
):
    # given
    room_list[0].channel_listings.all().update(visible_in_listings=False)

    room_count = Room.objects.count()

    # when
    data = _fetch_all_variants(
        staff_api_client, variables={"channel": channel_USD.slug}
    )

    assert data["totalCount"] == room_count - 1


def test_room_variants_visible_in_listings_by_staff_with_perm(
    staff_api_client, room_list, permission_manage_rooms, channel_USD
):
    # given
    room_list[0].channel_listings.all().update(visible_in_listings=False)

    room_count = Room.objects.count()

    # when
    data = _fetch_all_variants(
        staff_api_client,
        variables={"channel": channel_USD.slug},
        permissions=[permission_manage_rooms],
    )

    assert data["totalCount"] == room_count


def test_room_variants_visible_in_listings_by_app_without_perm(
    app_api_client, room_list, channel_USD
):
    # given
    room_list[0].channel_listings.all().update(visible_in_listings=False)

    room_count = Room.objects.count()

    # when
    data = _fetch_all_variants(app_api_client, variables={"channel": channel_USD.slug})

    assert data["totalCount"] == room_count - 1


def test_room_variants_visible_in_listings_by_app_with_perm(
    app_api_client, room_list, permission_manage_rooms, channel_USD
):
    # given
    room_list[0].channel_listings.all().update(visible_in_listings=False)

    room_count = Room.objects.count()

    # when
    data = _fetch_all_variants(
        app_api_client,
        variables={"channel": channel_USD.slug},
        permissions=[permission_manage_rooms],
    )

    assert data["totalCount"] == room_count


def _fetch_variant(client, variant, channel_slug=None, permissions=None):
    query = """
    query RoomVariantDetails($variantId: ID!, $channel: String) {
        roomVariant(id: $variantId, channel: $channel) {
            id
            room {
                id
            }
        }
    }
    """
    variables = {"variantId": graphene.Node.to_global_id("RoomVariant", variant.id)}
    if channel_slug:
        variables["channel"] = channel_slug
    response = client.post_graphql(
        query, variables, permissions=permissions, check_no_permissions=False
    )
    content = get_graphql_content(response)
    return content["data"]["roomVariant"]


def test_fetch_unpublished_variant_staff_user(
    staff_api_client, unavailable_room_with_variant, permission_manage_rooms
):
    variant = unavailable_room_with_variant.variants.first()
    data = _fetch_variant(
        staff_api_client,
        variant,
        permissions=[permission_manage_rooms],
    )

    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    room_id = graphene.Node.to_global_id(
        "Room", unavailable_room_with_variant.pk
    )

    assert data["id"] == variant_id
    assert data["room"]["id"] == room_id


def test_fetch_unpublished_variant_customer(
    user_api_client, unavailable_room_with_variant, channel_USD
):
    variant = unavailable_room_with_variant.variants.first()
    data = _fetch_variant(user_api_client, variant, channel_slug=channel_USD.slug)
    assert data is None


def test_fetch_unpublished_variant_anonymous_user(
    api_client, unavailable_room_with_variant, channel_USD
):
    variant = unavailable_room_with_variant.variants.first()
    data = _fetch_variant(api_client, variant, channel_slug=channel_USD.slug)
    assert data is None


ROOM_VARIANT_BULK_CREATE_MUTATION = """
    mutation RoomVariantBulkCreate(
        $variants: [RoomVariantBulkCreateInput]!, $roomId: ID!
    ) {
        roomVariantBulkCreate(variants: $variants, room: $roomId) {
            bulkRoomErrors {
                field
                message
                code
                index
                hotels
                channels
            }
            roomVariants{
                id
                name
                sku
                stocks {
                    hotel {
                        slug
                    }
                    quantity
                }
                channelListings {
                    channel {
                        slug
                    }
                    price {
                        currency
                        amount
                    }
                    costPrice {
                        currency
                        amount
                    }
                }
            }
            count
        }
    }
"""


def test_room_variant_bulk_create_by_attribute_id(
    staff_api_client, room, size_attribute, permission_manage_rooms
):
    room_variant_count = RoomVariant.objects.count()
    attribute_value_count = size_attribute.values.count()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    attribut_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    attribute_value = size_attribute.values.last()
    sku = str(uuid4())[:12]
    variants = [
        {
            "sku": sku,
            "weight": 2.5,
            "trackInventory": True,
            "attributes": [{"id": attribut_id, "values": [attribute_value.name]}],
        }
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert not data["bulkRoomErrors"]
    assert data["count"] == 1
    assert data["roomVariants"][0]["name"] == attribute_value.name
    assert room_variant_count + 1 == RoomVariant.objects.count()
    assert attribute_value_count == size_attribute.values.count()
    room_variant = RoomVariant.objects.get(sku=sku)
    room.refresh_from_db()
    assert room.default_variant == room_variant


def test_room_variant_bulk_create_only_not_variant_selection_attributes(
    staff_api_client, room, size_attribute, permission_manage_rooms
):
    """Ensure that sku is set as variant name when only variant selection attributes
    are assigned.
    """
    room_variant_count = RoomVariant.objects.count()
    attribute_value_count = size_attribute.values.count()

    size_attribute.input_type = AttributeInputType.MULTISELECT
    size_attribute.save(update_fields=["input_type"])

    room_id = graphene.Node.to_global_id("Room", room.pk)
    attribut_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)

    attribute_value = size_attribute.values.last()
    sku = str(uuid4())[:12]
    variants = [
        {
            "sku": sku,
            "weight": 2.5,
            "trackInventory": True,
            "attributes": [{"id": attribut_id, "values": [attribute_value.name]}],
        }
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert not data["bulkRoomErrors"]
    assert data["count"] == 1
    assert data["roomVariants"][0]["name"] == sku
    assert room_variant_count + 1 == RoomVariant.objects.count()
    assert attribute_value_count == size_attribute.values.count()
    room_variant = RoomVariant.objects.get(sku=sku)
    room.refresh_from_db()
    assert room.default_variant == room_variant


def test_room_variant_bulk_create_empty_attribute(
    staff_api_client, room, size_attribute, permission_manage_rooms
):
    room_variant_count = RoomVariant.objects.count()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    variants = [{"sku": str(uuid4())[:12], "attributes": []}]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert not data["bulkRoomErrors"]
    assert data["count"] == 1
    assert room_variant_count + 1 == RoomVariant.objects.count()


def test_room_variant_bulk_create_with_new_attribute_value(
    staff_api_client, room, size_attribute, permission_manage_rooms
):
    room_variant_count = RoomVariant.objects.count()
    attribute_value_count = size_attribute.values.count()
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    room_id = graphene.Node.to_global_id("Room", room.pk)
    attribute_value = size_attribute.values.last()
    variants = [
        {
            "sku": str(uuid4())[:12],
            "attributes": [{"id": size_attribute_id, "values": [attribute_value.name]}],
        },
        {
            "sku": str(uuid4())[:12],
            "attributes": [{"id": size_attribute_id, "values": ["Test-attribute"]}],
        },
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert not data["bulkRoomErrors"]
    assert data["count"] == 2
    assert room_variant_count + 2 == RoomVariant.objects.count()
    assert attribute_value_count + 1 == size_attribute.values.count()


def test_room_variant_bulk_create_variant_selection_and_other_attributes(
    staff_api_client,
    room,
    size_attribute,
    file_attribute,
    permission_manage_rooms,
):
    """Ensure that only values for variant selection attributes are required."""
    room_type = room.room_type
    room_type.variant_attributes.add(file_attribute)

    room_variant_count = RoomVariant.objects.count()
    attribute_value_count = size_attribute.values.count()

    room_id = graphene.Node.to_global_id("Room", room.pk)
    attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)

    attribute_value = size_attribute.values.last()
    sku = str(uuid4())[:12]
    variants = [
        {
            "sku": sku,
            "weight": 2.5,
            "trackInventory": True,
            "attributes": [{"id": attribute_id, "values": [attribute_value.name]}],
        }
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert not data["bulkRoomErrors"]
    assert data["count"] == 1
    assert room_variant_count + 1 == RoomVariant.objects.count()
    assert attribute_value_count == size_attribute.values.count()
    room_variant = RoomVariant.objects.get(sku=sku)
    room.refresh_from_db()
    assert room.default_variant == room_variant


def test_room_variant_bulk_create_stocks_input(
    staff_api_client, room, permission_manage_rooms, hotels, size_attribute
):
    room_variant_count = RoomVariant.objects.count()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    attribute_value_count = size_attribute.values.count()
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    attribute_value = size_attribute.values.last()
    variants = [
        {
            "sku": str(uuid4())[:12],
            "stocks": [
                {
                    "quantity": 10,
                    "hotel": graphene.Node.to_global_id(
                        "Hotel", hotels[0].pk
                    ),
                }
            ],
            "attributes": [{"id": size_attribute_id, "values": [attribute_value.name]}],
        },
        {
            "sku": str(uuid4())[:12],
            "attributes": [{"id": size_attribute_id, "values": ["Test-attribute"]}],
            "stocks": [
                {
                    "quantity": 15,
                    "hotel": graphene.Node.to_global_id(
                        "Hotel", hotels[0].pk
                    ),
                },
                {
                    "quantity": 15,
                    "hotel": graphene.Node.to_global_id(
                        "Hotel", hotels[1].pk
                    ),
                },
            ],
        },
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert not data["bulkRoomErrors"]
    assert data["count"] == 2
    assert room_variant_count + 2 == RoomVariant.objects.count()
    assert attribute_value_count + 1 == size_attribute.values.count()

    expected_result = {
        variants[0]["sku"]: {
            "sku": variants[0]["sku"],
            "stocks": [
                {
                    "hotel": {"slug": hotels[0].slug},
                    "quantity": variants[0]["stocks"][0]["quantity"],
                }
            ],
        },
        variants[1]["sku"]: {
            "sku": variants[1]["sku"],
            "stocks": [
                {
                    "hotel": {"slug": hotels[0].slug},
                    "quantity": variants[1]["stocks"][0]["quantity"],
                },
                {
                    "hotel": {"slug": hotels[1].slug},
                    "quantity": variants[1]["stocks"][1]["quantity"],
                },
            ],
        },
    }
    for variant_data in data["roomVariants"]:
        variant_data.pop("id")
        assert variant_data["sku"] in expected_result
        expected_variant = expected_result[variant_data["sku"]]
        expected_stocks = expected_variant["stocks"]
        assert all([stock in expected_stocks for stock in variant_data["stocks"]])


def test_room_variant_bulk_create_duplicated_hotels(
    staff_api_client, room, permission_manage_rooms, hotels, size_attribute
):
    room_id = graphene.Node.to_global_id("Room", room.pk)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    attribute_value = size_attribute.values.last()
    hotel1_id = graphene.Node.to_global_id("Hotel", hotels[0].pk)
    variants = [
        {
            "sku": str(uuid4())[:12],
            "stocks": [
                {
                    "quantity": 10,
                    "hotel": graphene.Node.to_global_id(
                        "Hotel", hotels[1].pk
                    ),
                }
            ],
            "attributes": [{"id": size_attribute_id, "values": [attribute_value.name]}],
        },
        {
            "sku": str(uuid4())[:12],
            "attributes": [{"id": size_attribute_id, "values": ["Test-attribute"]}],
            "stocks": [
                {"quantity": 15, "hotel": hotel1_id},
                {"quantity": 15, "hotel": hotel1_id},
            ],
        },
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    errors = data["bulkRoomErrors"]

    assert not data["roomVariants"]
    assert len(errors) == 1
    error = errors[0]
    assert error["field"] == "stocks"
    assert error["index"] == 1
    assert error["code"] == RoomErrorCode.DUPLICATED_INPUT_ITEM.name
    assert error["hotels"] == [hotel1_id]


def test_room_variant_bulk_create_channel_listings_input(
    staff_api_client,
    room_available_in_many_channels,
    permission_manage_rooms,
    hotels,
    size_attribute,
    channel_USD,
    channel_PLN,
):
    room = room_available_in_many_channels
    RoomChannelListing.objects.filter(room=room, channel=channel_PLN).update(
        is_published=False
    )
    room_variant_count = RoomVariant.objects.count()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    attribute_value_count = size_attribute.values.count()
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    attribute_value = size_attribute.values.last()
    variants = [
        {
            "sku": str(uuid4())[:12],
            "channelListings": [
                {
                    "price": 10.0,
                    "costPrice": 11.0,
                    "channelId": graphene.Node.to_global_id("Channel", channel_USD.pk),
                }
            ],
            "attributes": [{"id": size_attribute_id, "values": [attribute_value.name]}],
        },
        {
            "sku": str(uuid4())[:12],
            "attributes": [{"id": size_attribute_id, "values": ["Test-attribute"]}],
            "channelListings": [
                {
                    "price": 15.0,
                    "costPrice": 16.0,
                    "channelId": graphene.Node.to_global_id("Channel", channel_USD.pk),
                },
                {
                    "price": 12.0,
                    "costPrice": 13.0,
                    "channelId": graphene.Node.to_global_id("Channel", channel_PLN.pk),
                },
            ],
        },
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert not data["bulkRoomErrors"]
    assert data["count"] == 2
    assert room_variant_count + 2 == RoomVariant.objects.count()
    assert attribute_value_count + 1 == size_attribute.values.count()

    expected_result = {
        variants[0]["sku"]: {
            "sku": variants[0]["sku"],
            "channelListings": [
                {
                    "channel": {"slug": channel_USD.slug},
                    "price": {
                        "amount": variants[0]["channelListings"][0]["price"],
                        "currency": channel_USD.currency_code,
                    },
                    "costPrice": {
                        "amount": variants[0]["channelListings"][0]["costPrice"],
                        "currency": channel_USD.currency_code,
                    },
                }
            ],
        },
        variants[1]["sku"]: {
            "sku": variants[1]["sku"],
            "channelListings": [
                {
                    "channel": {"slug": channel_USD.slug},
                    "price": {
                        "amount": variants[1]["channelListings"][0]["price"],
                        "currency": channel_USD.currency_code,
                    },
                    "costPrice": {
                        "amount": variants[1]["channelListings"][0]["costPrice"],
                        "currency": channel_USD.currency_code,
                    },
                },
                {
                    "channel": {"slug": channel_PLN.slug},
                    "price": {
                        "amount": variants[1]["channelListings"][1]["price"],
                        "currency": channel_PLN.currency_code,
                    },
                    "costPrice": {
                        "amount": variants[1]["channelListings"][1]["costPrice"],
                        "currency": channel_PLN.currency_code,
                    },
                },
            ],
        },
    }
    for variant_data in data["roomVariants"]:
        variant_data.pop("id")
        assert variant_data["sku"] in expected_result
        expected_variant = expected_result[variant_data["sku"]]
        expected_channel_listing = expected_variant["channelListings"]
        assert all(
            [
                channelListing in expected_channel_listing
                for channelListing in variant_data["channelListings"]
            ]
        )


def test_room_variant_bulk_create_duplicated_channels(
    staff_api_client,
    room_available_in_many_channels,
    permission_manage_rooms,
    hotels,
    size_attribute,
    channel_USD,
):
    room = room_available_in_many_channels
    room_variant_count = RoomVariant.objects.count()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    attribute_value = size_attribute.values.last()
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.pk)
    variants = [
        {
            "sku": str(uuid4())[:12],
            "channelListings": [
                {"price": 10.0, "channelId": channel_id},
                {"price": 10.0, "channelId": channel_id},
            ],
            "attributes": [{"id": size_attribute_id, "values": [attribute_value.name]}],
        },
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert len(data["bulkRoomErrors"]) == 1
    error = data["bulkRoomErrors"][0]
    assert error["field"] == "channelListings"
    assert error["code"] == RoomErrorCode.DUPLICATED_INPUT_ITEM.name
    assert error["index"] == 0
    assert error["channels"] == [channel_id]
    assert room_variant_count == RoomVariant.objects.count()


def test_room_variant_bulk_create_too_many_decimal_places_in_price(
    staff_api_client,
    room_available_in_many_channels,
    permission_manage_rooms,
    size_attribute,
    channel_USD,
    channel_PLN,
):
    room = room_available_in_many_channels
    room_variant_count = RoomVariant.objects.count()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    attribute_value = size_attribute.values.last()
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.pk)
    channel_pln_id = graphene.Node.to_global_id("Channel", channel_PLN.pk)
    variants = [
        {
            "sku": str(uuid4())[:12],
            "channelListings": [
                {"price": 10.1234, "costPrice": 10.1234, "channelId": channel_id},
                {"price": 10.12345, "costPrice": 10.12345, "channelId": channel_pln_id},
            ],
            "attributes": [{"id": size_attribute_id, "values": [attribute_value.name]}],
        },
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert len(data["bulkRoomErrors"]) == 4
    errors = data["bulkRoomErrors"]
    assert errors[0]["field"] == "price"
    assert errors[0]["code"] == RoomErrorCode.INVALID.name
    assert errors[0]["index"] == 0
    assert errors[0]["channels"] == [channel_id]
    assert errors[1]["field"] == "price"
    assert errors[1]["code"] == RoomErrorCode.INVALID.name
    assert errors[1]["index"] == 0
    assert errors[1]["channels"] == [channel_pln_id]
    assert errors[2]["field"] == "costPrice"
    assert errors[2]["code"] == RoomErrorCode.INVALID.name
    assert errors[2]["index"] == 0
    assert errors[2]["channels"] == [channel_id]
    assert errors[3]["field"] == "costPrice"
    assert errors[3]["code"] == RoomErrorCode.INVALID.name
    assert errors[3]["index"] == 0
    assert errors[3]["channels"] == [channel_pln_id]
    assert room_variant_count == RoomVariant.objects.count()


def test_room_variant_bulk_create_room_not_assigned_to_channel(
    staff_api_client,
    room,
    permission_manage_rooms,
    hotels,
    size_attribute,
    channel_PLN,
):
    room_variant_count = RoomVariant.objects.count()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    assert not RoomChannelListing.objects.filter(
        room=room, channel=channel_PLN
    ).exists()
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    attribute_value = size_attribute.values.last()
    channel_id = graphene.Node.to_global_id("Channel", channel_PLN.pk)
    variants = [
        {
            "sku": str(uuid4())[:12],
            "channelListings": [{"price": 10.0, "channelId": channel_id}],
            "attributes": [{"id": size_attribute_id, "values": [attribute_value.name]}],
        },
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert len(data["bulkRoomErrors"]) == 1
    error = data["bulkRoomErrors"][0]
    assert error["field"] == "channelId"
    assert error["code"] == RoomErrorCode.ROOM_NOT_ASSIGNED_TO_CHANNEL.name
    assert error["index"] == 0
    assert error["channels"] == [channel_id]
    assert room_variant_count == RoomVariant.objects.count()


def test_room_variant_bulk_create_duplicated_sku(
    staff_api_client,
    room,
    room_with_default_variant,
    size_attribute,
    permission_manage_rooms,
):
    room_variant_count = RoomVariant.objects.count()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    sku = room.variants.first().sku
    sku2 = room_with_default_variant.variants.first().sku
    assert not sku == sku2
    variants = [
        {
            "sku": sku,
            "attributes": [{"id": size_attribute_id, "values": ["Test-value"]}],
        },
        {
            "sku": sku2,
            "attributes": [{"id": size_attribute_id, "values": ["Test-valuee"]}],
        },
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert len(data["bulkRoomErrors"]) == 2
    errors = data["bulkRoomErrors"]
    for index, error in enumerate(errors):
        assert error["field"] == "sku"
        assert error["code"] == RoomErrorCode.UNIQUE.name
        assert error["index"] == index
    assert room_variant_count == RoomVariant.objects.count()


def test_room_variant_bulk_create_duplicated_sku_in_input(
    staff_api_client, room, size_attribute, permission_manage_rooms
):
    room_variant_count = RoomVariant.objects.count()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    sku = str(uuid4())[:12]
    variants = [
        {
            "sku": sku,
            "attributes": [{"id": size_attribute_id, "values": ["Test-value"]}],
        },
        {
            "sku": sku,
            "attributes": [{"id": size_attribute_id, "values": ["Test-value2"]}],
        },
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert len(data["bulkRoomErrors"]) == 1
    error = data["bulkRoomErrors"][0]
    assert error["field"] == "sku"
    assert error["code"] == RoomErrorCode.UNIQUE.name
    assert error["index"] == 1
    assert room_variant_count == RoomVariant.objects.count()


def test_room_variant_bulk_create_many_errors(
    staff_api_client, room, size_attribute, permission_manage_rooms
):
    room_variant_count = RoomVariant.objects.count()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.pk)
    non_existent_attribute_pk = 0
    invalid_attribute_id = graphene.Node.to_global_id(
        "Attribute", non_existent_attribute_pk
    )
    sku = room.variants.first().sku
    variants = [
        {
            "sku": str(uuid4())[:12],
            "attributes": [{"id": size_attribute_id, "values": ["Test-value1"]}],
        },
        {
            "sku": str(uuid4())[:12],
            "attributes": [{"id": size_attribute_id, "values": ["Test-value4"]}],
        },
        {
            "sku": sku,
            "attributes": [{"id": size_attribute_id, "values": ["Test-value2"]}],
        },
        {
            "sku": str(uuid4())[:12],
            "attributes": [{"id": invalid_attribute_id, "values": ["Test-value3"]}],
        },
    ]

    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert len(data["bulkRoomErrors"]) == 2
    errors = data["bulkRoomErrors"]
    expected_errors = [
        {
            "field": "sku",
            "index": 2,
            "code": RoomErrorCode.UNIQUE.name,
            "message": ANY,
            "hotels": None,
            "channels": None,
        },
        {
            "field": "attributes",
            "index": 3,
            "code": RoomErrorCode.NOT_FOUND.name,
            "message": ANY,
            "hotels": None,
            "channels": None,
        },
    ]
    for expected_error in expected_errors:
        assert expected_error in errors
    assert room_variant_count == RoomVariant.objects.count()


def test_room_variant_bulk_create_two_variants_duplicated_attribute_value(
    staff_api_client,
    room_with_variant_with_two_attributes,
    color_attribute,
    size_attribute,
    permission_manage_rooms,
):
    room = room_with_variant_with_two_attributes
    room_variant_count = RoomVariant.objects.count()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    color_attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.id)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.id)
    variants = [
        {
            "sku": str(uuid4())[:12],
            "attributes": [
                {"id": color_attribute_id, "values": ["red"]},
                {"id": size_attribute_id, "values": ["small"]},
            ],
        }
    ]
    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert len(data["bulkRoomErrors"]) == 1
    error = data["bulkRoomErrors"][0]
    assert error["field"] == "attributes"
    assert error["code"] == RoomErrorCode.DUPLICATED_INPUT_ITEM.name
    assert error["index"] == 0
    assert room_variant_count == RoomVariant.objects.count()


def test_room_variant_bulk_create_two_variants_duplicated_attribute_value_in_input(
    staff_api_client,
    room_with_variant_with_two_attributes,
    permission_manage_rooms,
    color_attribute,
    size_attribute,
):
    room = room_with_variant_with_two_attributes
    room_id = graphene.Node.to_global_id("Room", room.pk)
    room_variant_count = RoomVariant.objects.count()
    color_attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.id)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.id)
    attributes = [
        {"id": color_attribute_id, "values": [color_attribute.values.last().slug]},
        {"id": size_attribute_id, "values": [size_attribute.values.last().slug]},
    ]
    variants = [
        {"sku": str(uuid4())[:12], "attributes": attributes},
        {"sku": str(uuid4())[:12], "attributes": attributes},
    ]
    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert len(data["bulkRoomErrors"]) == 1
    error = data["bulkRoomErrors"][0]
    assert error["field"] == "attributes"
    assert error["code"] == RoomErrorCode.DUPLICATED_INPUT_ITEM.name
    assert error["index"] == 1
    assert room_variant_count == RoomVariant.objects.count()


def test_room_variant_bulk_create_two_variants_duplicated_one_attribute_value(
    staff_api_client,
    room_with_variant_with_two_attributes,
    color_attribute,
    size_attribute,
    permission_manage_rooms,
):
    room = room_with_variant_with_two_attributes
    room_variant_count = RoomVariant.objects.count()
    room_id = graphene.Node.to_global_id("Room", room.pk)
    color_attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.id)
    size_attribute_id = graphene.Node.to_global_id("Attribute", size_attribute.id)
    variants = [
        {
            "sku": str(uuid4())[:12],
            "attributes": [
                {"id": color_attribute_id, "values": ["red"]},
                {"id": size_attribute_id, "values": ["big"]},
            ],
        }
    ]
    variables = {"roomId": room_id, "variants": variants}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(
        ROOM_VARIANT_BULK_CREATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert not data["bulkRoomErrors"]
    assert data["count"] == 1
    assert room_variant_count + 1 == RoomVariant.objects.count()


VARIANT_STOCKS_CREATE_MUTATION = """
    mutation RoomVariantStocksCreate($variantId: ID!, $stocks: [StockInput!]!){
        roomVariantStocksCreate(variantId: $variantId, stocks: $stocks){
            roomVariant{
                id
                stocks {
                    quantity
                    quantityAllocated
                    id
                    hotel{
                        slug
                    }
                }
            }
            bulkStockErrors{
                code
                field
                message
                index
            }
        }
    }
"""


def test_variant_stocks_create(
    staff_api_client, variant, hotel, permission_manage_rooms
):
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    stocks = [
        {
            "hotel": graphene.Node.to_global_id("Hotel", hotel.id),
            "quantity": 20,
        },
        {
            "hotel": graphene.Node.to_global_id("Hotel", second_hotel.id),
            "quantity": 100,
        },
    ]
    variables = {"variantId": variant_id, "stocks": stocks}
    response = staff_api_client.post_graphql(
        VARIANT_STOCKS_CREATE_MUTATION,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksCreate"]

    expected_result = [
        {
            "quantity": stocks[0]["quantity"],
            "quantityAllocated": 0,
            "hotel": {"slug": hotel.slug},
        },
        {
            "quantity": stocks[1]["quantity"],
            "quantityAllocated": 0,
            "hotel": {"slug": second_hotel.slug},
        },
    ]
    assert not data["bulkStockErrors"]
    assert len(data["roomVariant"]["stocks"]) == len(stocks)
    result = []
    for stock in data["roomVariant"]["stocks"]:
        stock.pop("id")
        result.append(stock)
    for res in result:
        assert res in expected_result


def test_variant_stocks_create_empty_stock_input(
    staff_api_client, variant, permission_manage_rooms
):
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)

    variables = {"variantId": variant_id, "stocks": []}
    response = staff_api_client.post_graphql(
        VARIANT_STOCKS_CREATE_MUTATION,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksCreate"]

    assert not data["bulkStockErrors"]
    assert len(data["roomVariant"]["stocks"]) == variant.stocks.count()
    assert data["roomVariant"]["id"] == variant_id


def test_variant_stocks_create_stock_already_exists(
    staff_api_client, variant, hotel, permission_manage_rooms
):
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    Stock.objects.create(room_variant=variant, hotel=hotel, quantity=10)

    stocks = [
        {
            "hotel": graphene.Node.to_global_id("Hotel", hotel.id),
            "quantity": 20,
        },
        {
            "hotel": graphene.Node.to_global_id("Hotel", second_hotel.id),
            "quantity": 100,
        },
    ]
    variables = {"variantId": variant_id, "stocks": stocks}
    response = staff_api_client.post_graphql(
        VARIANT_STOCKS_CREATE_MUTATION,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksCreate"]
    errors = data["bulkStockErrors"]

    assert errors
    assert errors[0]["code"] == StockErrorCode.UNIQUE.name
    assert errors[0]["field"] == "hotel"
    assert errors[0]["index"] == 0


def test_variant_stocks_create_stock_duplicated_hotel(
    staff_api_client, variant, hotel, permission_manage_rooms
):
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    second_hotel_id = graphene.Node.to_global_id("Hotel", second_hotel.id)

    stocks = [
        {
            "hotel": graphene.Node.to_global_id("Hotel", hotel.id),
            "quantity": 20,
        },
        {"hotel": second_hotel_id, "quantity": 100},
        {"hotel": second_hotel_id, "quantity": 120},
    ]
    variables = {"variantId": variant_id, "stocks": stocks}
    response = staff_api_client.post_graphql(
        VARIANT_STOCKS_CREATE_MUTATION,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksCreate"]
    errors = data["bulkStockErrors"]

    assert errors
    assert errors[0]["code"] == StockErrorCode.UNIQUE.name
    assert errors[0]["field"] == "hotel"
    assert errors[0]["index"] == 2


def test_variant_stocks_create_stock_duplicated_hotel_and_hotel_already_exists(
    staff_api_client, variant, hotel, permission_manage_rooms
):
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    second_hotel_id = graphene.Node.to_global_id("Hotel", second_hotel.id)
    Stock.objects.create(
        room_variant=variant, hotel=second_hotel, quantity=10
    )

    stocks = [
        {
            "hotel": graphene.Node.to_global_id("Hotel", hotel.id),
            "quantity": 20,
        },
        {"hotel": second_hotel_id, "quantity": 100},
        {"hotel": second_hotel_id, "quantity": 120},
    ]

    variables = {"variantId": variant_id, "stocks": stocks}
    response = staff_api_client.post_graphql(
        VARIANT_STOCKS_CREATE_MUTATION,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksCreate"]
    errors = data["bulkStockErrors"]

    assert len(errors) == 3
    assert {error["code"] for error in errors} == {
        StockErrorCode.UNIQUE.name,
    }
    assert {error["field"] for error in errors} == {
        "hotel",
    }
    assert {error["index"] for error in errors} == {1, 2}


VARIANT_STOCKS_UPDATE_MUTATIONS = """
    mutation RoomVariantStocksUpdate($variantId: ID!, $stocks: [StockInput!]!){
        roomVariantStocksUpdate(variantId: $variantId, stocks: $stocks){
            roomVariant{
                stocks{
                    quantity
                    quantityAllocated
                    id
                    hotel{
                        slug
                    }
                }
            }
            bulkStockErrors{
                code
                field
                message
                index
            }
        }
    }
"""


def test_room_variant_stocks_update(
    staff_api_client, variant, hotel, permission_manage_rooms
):
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    Stock.objects.create(room_variant=variant, hotel=hotel, quantity=10)

    stocks = [
        {
            "hotel": graphene.Node.to_global_id("Hotel", hotel.id),
            "quantity": 20,
        },
        {
            "hotel": graphene.Node.to_global_id("Hotel", second_hotel.id),
            "quantity": 100,
        },
    ]
    variables = {"variantId": variant_id, "stocks": stocks}
    response = staff_api_client.post_graphql(
        VARIANT_STOCKS_UPDATE_MUTATIONS,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksUpdate"]

    expected_result = [
        {
            "quantity": stocks[0]["quantity"],
            "quantityAllocated": 0,
            "hotel": {"slug": hotel.slug},
        },
        {
            "quantity": stocks[1]["quantity"],
            "quantityAllocated": 0,
            "hotel": {"slug": second_hotel.slug},
        },
    ]
    assert not data["bulkStockErrors"]
    assert len(data["roomVariant"]["stocks"]) == len(stocks)
    result = []
    for stock in data["roomVariant"]["stocks"]:
        stock.pop("id")
        result.append(stock)
    for res in result:
        assert res in expected_result


def test_room_variant_stocks_update_with_empty_stock_list(
    staff_api_client, variant, hotel, permission_manage_rooms
):
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    stocks = []
    variables = {"variantId": variant_id, "stocks": stocks}
    response = staff_api_client.post_graphql(
        VARIANT_STOCKS_UPDATE_MUTATIONS,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksUpdate"]

    assert not data["bulkStockErrors"]
    assert len(data["roomVariant"]["stocks"]) == len(stocks)


def test_variant_stocks_update_stock_duplicated_hotel(
    staff_api_client, variant, hotel, permission_manage_rooms
):
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    Stock.objects.create(room_variant=variant, hotel=hotel, quantity=10)

    stocks = [
        {
            "hotel": graphene.Node.to_global_id("Hotel", hotel.pk),
            "quantity": 20,
        },
        {
            "hotel": graphene.Node.to_global_id("Hotel", second_hotel.pk),
            "quantity": 100,
        },
        {
            "hotel": graphene.Node.to_global_id("Hotel", hotel.pk),
            "quantity": 150,
        },
    ]
    variables = {"variantId": variant_id, "stocks": stocks}
    response = staff_api_client.post_graphql(
        VARIANT_STOCKS_UPDATE_MUTATIONS,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksUpdate"]
    errors = data["bulkStockErrors"]

    assert errors
    assert errors[0]["code"] == StockErrorCode.UNIQUE.name
    assert errors[0]["field"] == "hotel"
    assert errors[0]["index"] == 2


VARIANT_STOCKS_DELETE_MUTATION = """
    mutation RoomVariantStocksDelete($variantId: ID!, $hotelIds: [ID!]!){
        roomVariantStocksDelete(
            variantId: $variantId, hotelIds: $hotelIds
        ){
            roomVariant{
                stocks{
                    id
                    quantity
                    hotel{
                        slug
                    }
                }
            }
            stockErrors{
                field
                code
                message
            }
        }
    }
"""


def test_room_variant_stocks_delete_mutation(
    staff_api_client, variant, hotel, permission_manage_rooms
):
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    Stock.objects.bulk_create(
        [
            Stock(room_variant=variant, hotel=hotel, quantity=10),
            Stock(room_variant=variant, hotel=second_hotel, quantity=140),
        ]
    )
    stocks_count = variant.stocks.count()

    hotel_ids = [graphene.Node.to_global_id("Hotel", second_hotel.id)]

    variables = {"variantId": variant_id, "hotelIds": hotel_ids}
    response = staff_api_client.post_graphql(
        VARIANT_STOCKS_DELETE_MUTATION,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksDelete"]

    variant.refresh_from_db()
    assert not data["stockErrors"]
    assert (
        len(data["roomVariant"]["stocks"])
        == variant.stocks.count()
        == stocks_count - 1
    )
    assert data["roomVariant"]["stocks"][0]["quantity"] == 10
    assert data["roomVariant"]["stocks"][0]["hotel"]["slug"] == hotel.slug


def test_room_variant_stocks_delete_mutation_invalid_hotel_id(
    staff_api_client, variant, hotel, permission_manage_rooms
):
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    Stock.objects.bulk_create(
        [Stock(room_variant=variant, hotel=hotel, quantity=10)]
    )
    stocks_count = variant.stocks.count()

    hotel_ids = [graphene.Node.to_global_id("Hotel", second_hotel.id)]

    variables = {"variantId": variant_id, "hotelIds": hotel_ids}
    response = staff_api_client.post_graphql(
        VARIANT_STOCKS_DELETE_MUTATION,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksDelete"]

    variant.refresh_from_db()
    assert not data["stockErrors"]
    assert (
        len(data["roomVariant"]["stocks"]) == variant.stocks.count() == stocks_count
    )
    assert data["roomVariant"]["stocks"][0]["quantity"] == 10
    assert data["roomVariant"]["stocks"][0]["hotel"]["slug"] == hotel.slug
