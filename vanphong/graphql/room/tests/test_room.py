import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import ANY, Mock, patch

import graphene
import pytest
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from freezegun import freeze_time
from graphql_relay import to_global_id
from measurement.measures import Weight
from prices import Money, TaxedMoney

from ....attribute import AttributeInputType, AttributeType
from ....attribute.models import Attribute, AttributeValue
from ....attribute.utils import associate_attribute_values_to_instance
from ....core.taxes import TaxType
from ....core.weight import WeightUnits
from ....order import OrderStatus
from ....order.models import OrderLine
from ....plugins.manager import PluginsManager
from ....room.error_codes import RoomErrorCode
from ....room.models import (
    Category,
    Collection,
    CollectionChannelListing,
    Room,
    RoomChannelListing,
    RoomImage,
    RoomType,
    RoomVariant,
    RoomVariantChannelListing,
)
from ....room.tasks import update_variants_names
from ....room.tests.utils import create_image, create_pdf_file_with_image_ext
from ....room.utils.costs import get_room_costs_data
from ....hotel.models import Allocation, Stock, Hotel
from ...core.enums import ReportingPeriod
from ...tests.utils import (
    assert_no_permission,
    get_graphql_content,
    get_graphql_content_from_response,
    get_multipart_request_body,
)
from ..bulk_mutations.rooms import RoomVariantStocksUpdate
from ..enums import VariantAttributeScope
from ..utils import create_stocks


@pytest.fixture
def query_rooms_with_filter():
    query = """
        query ($filter: RoomFilterInput!, $channel: String) {
          rooms(first:5, filter: $filter, channel: $channel) {
            edges{
              node{
                id
                name
              }
            }
          }
        }
        """
    return query


@pytest.fixture
def query_rooms_with_attributes():
    query = """
        query {
          rooms(first:5) {
            edges{
              node{
                id
                name
                attributes {
                    attribute {
                        id
                    }
                }
              }
            }
          }
        }
        """
    return query


@pytest.fixture
def query_collections_with_filter():
    query = """
    query ($filter: CollectionFilterInput!, $channel: String) {
          collections(first:5, filter: $filter, channel: $channel) {
            edges{
              node{
                id
                name
              }
            }
          }
        }
        """
    return query


@pytest.fixture
def query_categories_with_filter():
    query = """
    query ($filter: CategoryFilterInput!, ) {
          categories(first:5, filter: $filter) {
            totalCount
            edges{
              node{
                id
                name
              }
            }
          }
        }
        """
    return query


QUERY_FETCH_ALL_ROOMS = """
    query ($channel:String){
        rooms(first: 10, channel: $channel) {
            totalCount
            edges {
                node {
                    id
                    name
                }
            }
        }
    }
"""


QUERY_ROOM = """
    query ($id: ID, $slug: String, $channel:String){
        room(
            id: $id,
            slug: $slug,
            channel: $channel
        ) {
            id
            name
            weight {
                unit
                value
            }
            availableForPurchase
            isAvailableForPurchase
        }
    }
    """


def test_room_query_by_id_available_as_staff_user(
    staff_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }

    response = staff_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_id_not_available_as_staff_user(
    staff_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    response = staff_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_id_not_existing_in_channel_as_staff_user(
    staff_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).delete()

    response = staff_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is None


def test_room_query_by_id_as_staff_user_without_channel_slug(
    staff_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).delete()

    response = staff_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_id_available_as_app(
    app_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }

    response = app_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_id_not_available_as_app(
    app_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    response = app_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_id_not_existing_in_channel_as_app(
    app_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).delete()

    response = app_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is None


def test_room_query_by_id_as_app_without_channel_slug(
    app_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).delete()

    response = app_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


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


def test_get_collections_from_room_as_staff(
    staff_api_client,
    permission_manage_rooms,
    room_with_collections,
    channel_USD,
):
    # given
    room = room_with_collections
    variables = {"id": graphene.Node.to_global_id("Room", room.pk)}

    # when
    response = staff_api_client.post_graphql(
        QUERY_COLLECTION_FROM_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    collections = content["data"]["room"]["collections"]
    assert len(collections) == 3
    for collection in room.collections.all():
        assert {"name": collection.name} in collections


def test_get_collections_from_room_as_app(
    app_api_client,
    permission_manage_rooms,
    room_with_collections,
    channel_USD,
):
    # given
    room = room_with_collections
    variables = {"id": graphene.Node.to_global_id("Room", room.pk)}

    # when
    response = app_api_client.post_graphql(
        QUERY_COLLECTION_FROM_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    collections = content["data"]["room"]["collections"]
    assert len(collections) == 3
    for collection in room.collections.all():
        assert {"name": collection.name} in collections


def test_get_collections_from_room_as_customer(
    user_api_client, room_with_collections, channel_USD, published_collection
):
    # given
    room = room_with_collections
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }

    # when
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


def test_get_collections_from_room_as_anonymous(
    api_client, room_with_collections, channel_USD, published_collection
):
    # given
    room = room_with_collections
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }

    # when
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


def test_room_query_by_id_available_as_customer(
    user_api_client, room, channel_USD
):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }

    # when
    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_id_not_available_as_customer(
    user_api_client, room, channel_USD
):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is None


def test_room_unpublished_query_by_id_as_app(
    app_api_client, unavailable_room, permission_manage_rooms, channel_USD
):
    # given
    variables = {
        "id": graphene.Node.to_global_id("Room", unavailable_room.pk),
        "channel": channel_USD.slug,
    }

    # when
    response = app_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == unavailable_room.name


def test_room_query_by_id_weight_returned_in_default_unit(
    user_api_client, room, site_settings, channel_USD
):
    # given
    room.weight = Weight(kg=10)
    room.save(update_fields=["weight"])

    site_settings.default_weight_unit = WeightUnits.POUND
    site_settings.save(update_fields=["default_weight_unit"])

    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }

    # when
    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name
    assert room_data["weight"]["value"] == 22.046
    assert room_data["weight"]["unit"] == WeightUnits.POUND.upper()


def test_room_query_by_id_weight_is_rounded(
    user_api_client, room, site_settings, channel_USD
):
    # given
    room.weight = Weight(kg=1.83456)
    room.save(update_fields=["weight"])

    site_settings.default_weight_unit = WeightUnits.KILOGRAM
    site_settings.save(update_fields=["default_weight_unit"])

    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }

    # when
    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name
    assert room_data["weight"]["value"] == 1.835
    assert room_data["weight"]["unit"] == WeightUnits.KILOGRAM.upper()


def test_room_query_by_slug(user_api_client, room, channel_USD):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is None


def test_room_query_by_id_not_existing_in_channel_as_customer(
    user_api_client, room, channel_USD
):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).delete()

    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is None


def test_room_query_by_slug_available_as_staff_user(
    staff_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "slug": room.slug,
        "channel": channel_USD.slug,
    }

    response = staff_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_slug_not_available_as_staff_user(
    staff_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "slug": room.slug,
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    response = staff_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_slug_not_existing_in_channel_as_staff_user(
    staff_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "slug": room.slug,
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).delete()

    response = staff_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is None


def test_room_query_by_slug_as_staff_user_without_channel(
    staff_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "slug": room.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).delete()

    response = staff_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_slug_available_as_app(
    app_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "slug": room.slug,
        "channel": channel_USD.slug,
    }

    response = app_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_slug_not_available_as_app(
    app_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "slug": room.slug,
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    response = app_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_slug_not_existing_in_channel_as_app(
    app_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "slug": room.slug,
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).delete()

    response = app_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is None


def test_room_query_by_slug_as_app_without_channel(
    app_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {
        "slug": room.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).delete()

    response = app_api_client.post_graphql(
        QUERY_ROOM,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_slug_available_as_customer(
    user_api_client, room, channel_USD
):
    variables = {
        "slug": room.slug,
        "channel": channel_USD.slug,
    }

    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_by_slug_not_available_as_customer(
    user_api_client, room, channel_USD
):
    variables = {
        "slug": room.slug,
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is None


def test_room_query_is_available_for_purchase_true(
    user_api_client, room, channel_USD
):
    # given
    available_for_purchase = datetime.today() - timedelta(days=1)
    room.channel_listings.update(available_for_purchase=available_for_purchase)

    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }

    # when
    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["room"]

    assert room_data["availableForPurchase"] == available_for_purchase.strftime(
        "%Y-%m-%d"
    )
    assert room_data["isAvailableForPurchase"] is True


def test_room_query_is_available_for_purchase_false(
    user_api_client, room, channel_USD
):
    # given
    available_for_purchase = datetime.today() + timedelta(days=1)
    room.channel_listings.update(available_for_purchase=available_for_purchase)

    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }

    # when
    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["room"]

    assert room_data["availableForPurchase"] == available_for_purchase.strftime(
        "%Y-%m-%d"
    )
    assert room_data["isAvailableForPurchase"] is False


def test_room_query_is_available_for_purchase_false_no_available_for_purchase_date(
    user_api_client, room, channel_USD
):
    # given
    room.channel_listings.update(available_for_purchase=None)

    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }

    # when
    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["room"]

    assert not room_data["availableForPurchase"]
    assert room_data["isAvailableForPurchase"] is False


def test_room_query_unpublished_rooms_by_slug(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    # given
    user = staff_api_client.user
    user.user_permissions.add(permission_manage_rooms)

    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )
    variables = {
        "slug": room.slug,
        "channel": channel_USD.slug,
    }

    # when
    response = staff_api_client.post_graphql(QUERY_ROOM, variables=variables)

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_unpublished_rooms_by_slug_and_anonymous_user(
    api_client, room, channel_USD
):
    # given
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )
    variables = {
        "slug": room.slug,
        "channel": channel_USD.slug,
    }

    # when
    response = api_client.post_graphql(QUERY_ROOM, variables=variables)

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is None


def test_room_query_by_slug_not_existing_in_channel_as_customer(
    user_api_client, room, channel_USD
):
    variables = {
        "slug": room.slug,
        "channel": channel_USD.slug,
    }
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).delete()

    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is None


QUERY_ROOM_WITHOUT_CHANNEL = """
    query ($id: ID){
        room(
            id: $id
        ) {
            id
            name
        }
    }
    """


def test_room_query_by_id_without_channel_not_available_as_staff_user(
    staff_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {"id": graphene.Node.to_global_id("Room", room.pk)}
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    response = staff_api_client.post_graphql(
        QUERY_ROOM_WITHOUT_CHANNEL,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    assert room_data is not None
    assert room_data["name"] == room.name


def test_room_query_error_when_id_and_slug_provided(
    user_api_client,
    room,
    graphql_log_handler,
):
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "slug": room.slug,
    }
    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)
    assert graphql_log_handler.messages == [
        "vanphong.graphql.errors.handled[INFO].GraphQLError"
    ]
    content = get_graphql_content(response, ignore_errors=True)
    assert len(content["errors"]) == 1


def test_room_query_error_when_no_param(
    user_api_client,
    room,
    graphql_log_handler,
):
    variables = {}
    response = user_api_client.post_graphql(QUERY_ROOM, variables=variables)
    assert graphql_log_handler.messages == [
        "vanphong.graphql.errors.handled[INFO].GraphQLError"
    ]
    content = get_graphql_content(response, ignore_errors=True)
    assert len(content["errors"]) == 1


def test_fetch_all_rooms_available_as_staff_user(
    staff_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {"channel": channel_USD.slug}
    response = staff_api_client.post_graphql(
        QUERY_FETCH_ALL_ROOMS,
        variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    num_rooms = Room.objects.count()
    assert content["data"]["rooms"]["totalCount"] == num_rooms
    assert len(content["data"]["rooms"]["edges"]) == num_rooms


def test_fetch_all_rooms_not_available_as_staff_user(
    staff_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {"channel": channel_USD.slug}
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    response = staff_api_client.post_graphql(
        QUERY_FETCH_ALL_ROOMS,
        variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    num_rooms = Room.objects.count()
    assert content["data"]["rooms"]["totalCount"] == num_rooms
    assert len(content["data"]["rooms"]["edges"]) == num_rooms


def test_fetch_all_rooms_not_existing_in_channel_as_staff_user(
    staff_api_client, permission_manage_rooms, channel_USD, room_list
):
    variables = {"channel": channel_USD.slug}
    RoomChannelListing.objects.filter(
        room=room_list[0], channel=channel_USD
    ).delete()

    response = staff_api_client.post_graphql(
        QUERY_FETCH_ALL_ROOMS,
        variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)

    # if channel slug is provided we return all rooms related to this channel
    num_rooms = Room.objects.count() - 1

    assert content["data"]["rooms"]["totalCount"] == num_rooms
    assert len(content["data"]["rooms"]["edges"]) == num_rooms


def test_fetch_all_rooms_as_staff_user_without_channel_slug(
    staff_api_client, permission_manage_rooms, room_list, channel_USD
):
    RoomChannelListing.objects.filter(
        room=room_list[0], channel=channel_USD
    ).delete()

    response = staff_api_client.post_graphql(
        QUERY_FETCH_ALL_ROOMS,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    num_rooms = Room.objects.count()
    assert content["data"]["rooms"]["totalCount"] == num_rooms
    assert len(content["data"]["rooms"]["edges"]) == num_rooms


def test_fetch_all_rooms_available_as_app(
    app_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {"channel": channel_USD.slug}
    response = app_api_client.post_graphql(
        QUERY_FETCH_ALL_ROOMS,
        variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    num_rooms = Room.objects.count()
    assert content["data"]["rooms"]["totalCount"] == num_rooms
    assert len(content["data"]["rooms"]["edges"]) == num_rooms


def test_fetch_all_rooms_not_available_as_app(
    app_api_client, permission_manage_rooms, room, channel_USD
):
    variables = {"channel": channel_USD.slug}
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    response = app_api_client.post_graphql(
        QUERY_FETCH_ALL_ROOMS,
        variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    num_rooms = Room.objects.count()
    assert content["data"]["rooms"]["totalCount"] == num_rooms
    assert len(content["data"]["rooms"]["edges"]) == num_rooms


def test_fetch_all_rooms_not_existing_in_channel_as_app(
    app_api_client, permission_manage_rooms, room_list, channel_USD
):
    variables = {"channel": channel_USD.slug}
    RoomChannelListing.objects.filter(
        room=room_list[0], channel=channel_USD
    ).delete()

    response = app_api_client.post_graphql(
        QUERY_FETCH_ALL_ROOMS,
        variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    # if channel slug is provided we return all rooms related to this channel

    num_rooms = Room.objects.count() - 1
    assert content["data"]["rooms"]["totalCount"] == num_rooms
    assert len(content["data"]["rooms"]["edges"]) == num_rooms


def test_fetch_all_rooms_as_app_without_channel_slug(
    app_api_client, permission_manage_rooms, room_list, channel_USD
):
    RoomChannelListing.objects.filter(
        room=room_list[0], channel=channel_USD
    ).delete()

    response = app_api_client.post_graphql(
        QUERY_FETCH_ALL_ROOMS,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )
    content = get_graphql_content(response)
    num_rooms = Room.objects.count()
    assert content["data"]["rooms"]["totalCount"] == num_rooms
    assert len(content["data"]["rooms"]["edges"]) == num_rooms


def test_fetch_all_rooms_available_as_customer(
    user_api_client, room, channel_USD
):
    variables = {"channel": channel_USD.slug}
    response = user_api_client.post_graphql(QUERY_FETCH_ALL_ROOMS, variables)
    content = get_graphql_content(response)
    num_rooms = Room.objects.count()
    assert content["data"]["rooms"]["totalCount"] == num_rooms
    assert len(content["data"]["rooms"]["edges"]) == num_rooms


def test_fetch_all_rooms_not_available_as_customer(
    user_api_client, room, channel_USD
):
    variables = {"channel": channel_USD.slug}
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    response = user_api_client.post_graphql(
        QUERY_FETCH_ALL_ROOMS,
        variables,
    )
    content = get_graphql_content(response)
    assert content["data"]["rooms"]["totalCount"] == 0
    assert not content["data"]["rooms"]["edges"]


def test_fetch_all_rooms_not_existing_in_channel_as_customer(
    user_api_client, room, channel_USD
):
    variables = {"channel": channel_USD.slug}
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).delete()

    response = user_api_client.post_graphql(QUERY_FETCH_ALL_ROOMS, variables)
    content = get_graphql_content(response)
    assert content["data"]["rooms"]["totalCount"] == 0
    assert not content["data"]["rooms"]["edges"]


def test_fetch_all_rooms_available_as_anonymous(api_client, room, channel_USD):
    variables = {"channel": channel_USD.slug}
    response = api_client.post_graphql(QUERY_FETCH_ALL_ROOMS, variables)
    content = get_graphql_content(response)
    num_rooms = Room.objects.count()
    assert content["data"]["rooms"]["totalCount"] == num_rooms
    assert len(content["data"]["rooms"]["edges"]) == num_rooms


def test_fetch_all_rooms_not_available_as_anonymous(
    api_client, room, channel_USD
):
    variables = {"channel": channel_USD.slug}
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    response = api_client.post_graphql(
        QUERY_FETCH_ALL_ROOMS,
        variables,
    )
    content = get_graphql_content(response)
    assert content["data"]["rooms"]["totalCount"] == 0
    assert not content["data"]["rooms"]["edges"]


def test_fetch_all_rooms_not_existing_in_channel_as_anonymous(
    api_client, room, channel_USD
):
    variables = {"channel": channel_USD.slug}
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).delete()

    response = api_client.post_graphql(QUERY_FETCH_ALL_ROOMS, variables)
    content = get_graphql_content(response)
    assert content["data"]["rooms"]["totalCount"] == 0
    assert not content["data"]["rooms"]["edges"]


def test_fetch_all_rooms_visible_in_listings(
    user_api_client, room_list, permission_manage_rooms, channel_USD
):
    # given
    room_list[0].channel_listings.update(visible_in_listings=False)

    room_count = Room.objects.count()
    variables = {"channel": channel_USD.slug}

    # when
    response = user_api_client.post_graphql(QUERY_FETCH_ALL_ROOMS, variables)

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["rooms"]["edges"]
    assert len(room_data) == room_count - 1
    rooms_ids = [room["node"]["id"] for room in room_data]
    assert graphene.Node.to_global_id("Room", room_list[0].pk) not in rooms_ids


def test_fetch_all_rooms_visible_in_listings_by_staff_with_perm(
    staff_api_client, room_list, permission_manage_rooms, channel_USD
):
    # given
    room_list[0].channel_listings.update(visible_in_listings=False)

    room_count = Room.objects.count()
    variables = {"channel": channel_USD.slug}

    # when
    response = staff_api_client.post_graphql(
        QUERY_FETCH_ALL_ROOMS,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["rooms"]["edges"]
    assert len(room_data) == room_count


def test_fetch_all_rooms_visible_in_listings_by_staff_without_manage_rooms(
    staff_api_client, room_list, channel_USD
):
    # given
    room_list[0].channel_listings.update(visible_in_listings=False)

    room_count = Room.objects.count()
    variables = {"channel": channel_USD.slug}

    # when
    response = staff_api_client.post_graphql(QUERY_FETCH_ALL_ROOMS, variables)

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["rooms"]["edges"]
    assert len(room_data) == room_count


def test_fetch_all_rooms_visible_in_listings_by_app_with_perm(
    app_api_client, room_list, permission_manage_rooms, channel_USD
):
    # given
    room_list[0].channel_listings.update(visible_in_listings=False)

    room_count = Room.objects.count()
    variables = {"channel": channel_USD.slug}

    # when
    response = app_api_client.post_graphql(
        QUERY_FETCH_ALL_ROOMS,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["rooms"]["edges"]
    assert len(room_data) == room_count


def test_fetch_all_rooms_visible_in_listings_by_app_without_manage_rooms(
    app_api_client, room_list, channel_USD
):
    # given
    room_list[0].channel_listings.update(visible_in_listings=False)

    room_count = Room.objects.count()
    variables = {"channel": channel_USD.slug}

    # when
    response = app_api_client.post_graphql(QUERY_FETCH_ALL_ROOMS, variables)

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["rooms"]["edges"]
    assert len(room_data) == room_count


def test_fetch_room_from_category_query(
    staff_api_client, room, permission_manage_rooms, stock, channel_USD
):
    category = Category.objects.first()
    room = category.rooms.first()
    query = """
    query {
        category(id: "%(category_id)s") {
            rooms(first: 20, channel: "%(channel_slug)s") {
                edges {
                    node {
                        id
                        name
                        url
                        slug
                        thumbnail{
                            url
                            alt
                        }
                        images {
                            url
                        }
                        variants {
                            name
                            channelListings {
                                costPrice {
                                    amount
                                }
                            }
                        }
                        channelListings {
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
                        }
                        isAvailable
                        pricing {
                            priceRange {
                                start {
                                    gross {
                                        amount
                                        currency
                                        localized
                                    }
                                    net {
                                        amount
                                        currency
                                        localized
                                    }
                                    currency
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """ % {
        "category_id": graphene.Node.to_global_id("Category", category.id),
        "channel_slug": channel_USD.slug,
    }
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query)
    content = get_graphql_content(response)
    assert content["data"]["category"] is not None
    room_edges_data = content["data"]["category"]["rooms"]["edges"]
    assert len(room_edges_data) == category.rooms.count()
    room_data = room_edges_data[0]["node"]
    assert room_data["name"] == room.name
    assert room_data["url"] == ""
    assert room_data["slug"] == room.slug

    variant = room.variants.first()
    variant_channel_listing = variant.channel_listings.filter(channel_id=channel_USD.id)
    purchase_cost, margin = get_room_costs_data(
        variant_channel_listing, True, channel_USD.currency_code
    )
    cost_start = room_data["channelListings"][0]["purchaseCost"]["start"]["amount"]
    cost_stop = room_data["channelListings"][0]["purchaseCost"]["stop"]["amount"]

    assert purchase_cost.start.amount == cost_start
    assert purchase_cost.stop.amount == cost_stop
    assert room_data["isAvailable"] is True
    assert margin[0] == room_data["channelListings"][0]["margin"]["start"]
    assert margin[1] == room_data["channelListings"][0]["margin"]["stop"]

    variant = room.variants.first()
    variant_channel_listing = variant.channel_listings.get(channel_id=channel_USD.id)
    variant_channel_data = room_data["variants"][0]["channelListings"][0]
    variant_cost = variant_channel_data["costPrice"]["amount"]

    assert variant_channel_listing.cost_price.amount == variant_cost


def test_rooms_query_with_filter_attributes(
    query_rooms_with_filter, staff_api_client, room, permission_manage_rooms
):

    room_type = RoomType.objects.create(
        name="Custom Type",
        slug="custom-type",
        has_variants=True,
        is_shipping_required=True,
    )
    attribute = Attribute.objects.create(slug="new_attr", name="Attr")
    attribute.room_types.add(room_type)
    attr_value = AttributeValue.objects.create(
        attribute=attribute, name="First", slug="first"
    )
    second_room = room
    second_room.id = None
    second_room.room_type = room_type
    second_room.slug = "second-room"
    second_room.save()
    associate_attribute_values_to_instance(second_room, attribute, attr_value)

    variables = {
        "filter": {"attributes": [{"slug": attribute.slug, "value": attr_value.slug}]}
    }

    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query_rooms_with_filter, variables)
    content = get_graphql_content(response)
    second_room_id = graphene.Node.to_global_id("Room", second_room.id)
    rooms = content["data"]["rooms"]["edges"]

    assert len(rooms) == 1
    assert rooms[0]["node"]["id"] == second_room_id
    assert rooms[0]["node"]["name"] == second_room.name


def test_rooms_query_with_filter_room_type(
    query_rooms_with_filter, staff_api_client, room, permission_manage_rooms
):
    room_type = RoomType.objects.create(
        name="Custom Type",
        slug="custom-type",
        has_variants=True,
        is_shipping_required=True,
    )
    second_room = room
    second_room.id = None
    second_room.room_type = room_type
    second_room.slug = "second-room"
    second_room.save()

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.id)
    variables = {"filter": {"roomType": room_type_id}}

    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query_rooms_with_filter, variables)
    content = get_graphql_content(response)
    second_room_id = graphene.Node.to_global_id("Room", second_room.id)
    rooms = content["data"]["rooms"]["edges"]

    assert len(rooms) == 1
    assert rooms[0]["node"]["id"] == second_room_id
    assert rooms[0]["node"]["name"] == second_room.name


def test_rooms_query_with_filter_category(
    query_rooms_with_filter, staff_api_client, room, permission_manage_rooms
):
    category = Category.objects.create(name="Custom", slug="custom")
    second_room = room
    second_room.id = None
    second_room.slug = "second-room"
    second_room.category = category
    second_room.save()

    category_id = graphene.Node.to_global_id("Category", category.id)
    variables = {"filter": {"categories": [category_id]}}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query_rooms_with_filter, variables)
    content = get_graphql_content(response)
    second_room_id = graphene.Node.to_global_id("Room", second_room.id)
    rooms = content["data"]["rooms"]["edges"]

    assert len(rooms) == 1
    assert rooms[0]["node"]["id"] == second_room_id
    assert rooms[0]["node"]["name"] == second_room.name


def test_rooms_query_with_filter_has_category_false(
    query_rooms_with_filter, staff_api_client, room, permission_manage_rooms
):
    second_room = room
    second_room.category = None
    second_room.id = None
    second_room.slug = "second-room"
    second_room.save()

    variables = {"filter": {"hasCategory": False}}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query_rooms_with_filter, variables)
    content = get_graphql_content(response)
    second_room_id = graphene.Node.to_global_id("Room", second_room.id)
    rooms = content["data"]["rooms"]["edges"]

    assert len(rooms) == 1
    assert rooms[0]["node"]["id"] == second_room_id
    assert rooms[0]["node"]["name"] == second_room.name


def test_rooms_query_with_filter_has_category_true(
    query_rooms_with_filter,
    staff_api_client,
    room_without_category,
    permission_manage_rooms,
):
    category = Category.objects.create(name="Custom", slug="custom")
    second_room = room_without_category
    second_room.category = category
    second_room.id = None
    second_room.slug = "second-room"
    second_room.save()

    variables = {"filter": {"hasCategory": True}}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query_rooms_with_filter, variables)
    content = get_graphql_content(response)
    second_room_id = graphene.Node.to_global_id("Room", second_room.id)
    rooms = content["data"]["rooms"]["edges"]

    assert len(rooms) == 1
    assert rooms[0]["node"]["id"] == second_room_id
    assert rooms[0]["node"]["name"] == second_room.name


def test_rooms_query_with_filter_collection(
    query_rooms_with_filter,
    staff_api_client,
    room,
    collection,
    permission_manage_rooms,
):
    second_room = room
    second_room.id = None
    second_room.slug = "second-room"
    second_room.save()
    second_room.collections.add(collection)

    collection_id = graphene.Node.to_global_id("Collection", collection.id)
    variables = {"filter": {"collections": [collection_id]}}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query_rooms_with_filter, variables)
    content = get_graphql_content(response)
    second_room_id = graphene.Node.to_global_id("Room", second_room.id)
    rooms = content["data"]["rooms"]["edges"]

    assert len(rooms) == 1
    assert rooms[0]["node"]["id"] == second_room_id
    assert rooms[0]["node"]["name"] == second_room.name


def test_rooms_query_with_filter_category_and_search(
    query_rooms_with_filter,
    staff_api_client,
    room,
    permission_manage_rooms,
):
    category = Category.objects.create(name="Custom", slug="custom")
    second_room = room
    second_room.id = None
    second_room.slug = "second-room"
    second_room.category = category
    room.category = category
    second_room.save()
    room.save()

    category_id = graphene.Node.to_global_id("Category", category.id)
    variables = {"filter": {"categories": [category_id], "search": room.name}}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query_rooms_with_filter, variables)
    content = get_graphql_content(response)
    room_id = graphene.Node.to_global_id("Room", room.id)
    rooms = content["data"]["rooms"]["edges"]

    assert len(rooms) == 1
    assert rooms[0]["node"]["id"] == room_id
    assert rooms[0]["node"]["name"] == room.name


def test_rooms_with_variants_query_as_app(
    query_rooms_with_attributes,
    app_api_client,
    room_with_multiple_values_attributes,
    permission_manage_rooms,
):
    room = room_with_multiple_values_attributes
    attribute = room.attributes.first().attribute
    attribute.visible_in_storefront = False
    attribute.save()
    second_room = room
    second_room.id = None
    second_room.slug = "second-room"
    second_room.save()
    room.save()

    app_api_client.app.permissions.add(permission_manage_rooms)
    response = app_api_client.post_graphql(query_rooms_with_attributes)
    content = get_graphql_content(response)
    rooms = content["data"]["rooms"]["edges"]
    assert len(rooms) == 2
    attribute_id = graphene.Node.to_global_id("Attribute", attribute.id)
    for response_room in rooms:
        attrs = response_room["node"]["attributes"]
        assert len(attrs) == 1
        assert attrs[0]["attribute"]["id"] == attribute_id


@pytest.mark.parametrize(
    "rooms_filter",
    [
        {"price": {"gte": 1.0, "lte": 2.0}},
        {"minimalPrice": {"gte": 1.0, "lte": 2.0}},
        {"isPublished": False},
        {"search": "Juice1"},
    ],
)
def test_rooms_query_with_filter(
    rooms_filter,
    query_rooms_with_filter,
    staff_api_client,
    room,
    permission_manage_rooms,
    channel_USD,
):
    assert "Juice1" not in room.name

    second_room = room
    second_room.id = None
    second_room.name = "Apple Juice1"
    second_room.slug = "apple-juice1"
    second_room.save()
    variant_second_room = second_room.variants.create(
        room=second_room,
        sku=second_room.slug,
    )
    RoomVariantChannelListing.objects.create(
        variant=variant_second_room,
        channel=channel_USD,
        price_amount=Decimal(1.99),
        cost_price_amount=Decimal(1),
        currency=channel_USD.currency_code,
    )
    RoomChannelListing.objects.create(
        room=second_room,
        channel=channel_USD,
        is_published=True,
    )
    variables = {"filter": {"search": "Juice1"}, "channel": channel_USD.slug}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query_rooms_with_filter, variables)
    content = get_graphql_content(response)
    second_room_id = graphene.Node.to_global_id("Room", second_room.id)
    rooms = content["data"]["rooms"]["edges"]

    assert len(rooms) == 1
    assert rooms[0]["node"]["id"] == second_room_id
    assert rooms[0]["node"]["name"] == second_room.name


@pytest.mark.parametrize("is_published", [(True), (False)])
def test_rooms_query_with_filter_search_by_sku(
    is_published,
    query_rooms_with_filter,
    staff_api_client,
    room_with_two_variants,
    room_with_default_variant,
    permission_manage_rooms,
    channel_USD,
):
    RoomChannelListing.objects.filter(
        room=room_with_default_variant, channel=channel_USD
    ).update(is_published=is_published)
    variables = {"filter": {"search": "1234"}}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query_rooms_with_filter, variables)
    content = get_graphql_content(response)
    room_id = graphene.Node.to_global_id("Room", room_with_default_variant.id)
    rooms = content["data"]["rooms"]["edges"]

    assert len(rooms) == 1
    assert rooms[0]["node"]["id"] == room_id
    assert rooms[0]["node"]["name"] == room_with_default_variant.name


def test_rooms_query_with_filter_stock_availability(
    query_rooms_with_filter,
    staff_api_client,
    room,
    order_line,
    permission_manage_rooms,
):
    stock = room.variants.first().stocks.first()
    Allocation.objects.create(
        order_line=order_line, stock=stock, quantity_allocated=stock.quantity
    )
    variables = {"filter": {"stockAvailability": "OUT_OF_STOCK"}}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query_rooms_with_filter, variables)
    content = get_graphql_content(response)
    room_id = graphene.Node.to_global_id("Room", room.id)
    rooms = content["data"]["rooms"]["edges"]

    assert len(rooms) == 1
    assert rooms[0]["node"]["id"] == room_id
    assert rooms[0]["node"]["name"] == room.name


@pytest.mark.parametrize(
    "quantity_input, hotel_indexes, count, indexes_of_rooms_in_result",
    [
        ({"lte": "80", "gte": "20"}, [1, 2], 1, [1]),
        ({"lte": "120", "gte": "40"}, [1, 2], 1, [0]),
        ({"gte": "10"}, [1], 1, [1]),
        ({"gte": "110"}, [2], 0, []),
        (None, [1], 1, [1]),
        (None, [2], 2, [0, 1]),
        ({"lte": "210", "gte": "70"}, [], 1, [0]),
        ({"lte": "90"}, [], 1, [1]),
        ({"lte": "90", "gte": "75"}, [], 0, []),
    ],
)
def test_rooms_query_with_filter_stocks(
    quantity_input,
    hotel_indexes,
    count,
    indexes_of_rooms_in_result,
    query_rooms_with_filter,
    staff_api_client,
    room_with_single_variant,
    room_with_two_variants,
    hotel,
    channel_USD,
):
    room1 = room_with_single_variant
    room2 = room_with_two_variants
    rooms = [room1, room2]

    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    third_hotel = Hotel.objects.get(pk=hotel.pk)
    third_hotel.slug = "third hotel"
    third_hotel.pk = None
    third_hotel.save()

    hotels = [hotel, second_hotel, third_hotel]
    hotel_pks = [
        graphene.Node.to_global_id("Hotel", hotels[index].pk)
        for index in hotel_indexes
    ]

    Stock.objects.bulk_create(
        [
            Stock(
                hotel=third_hotel,
                room_variant=room1.variants.first(),
                quantity=100,
            ),
            Stock(
                hotel=second_hotel,
                room_variant=room2.variants.first(),
                quantity=10,
            ),
            Stock(
                hotel=third_hotel,
                room_variant=room2.variants.first(),
                quantity=25,
            ),
            Stock(
                hotel=third_hotel,
                room_variant=room2.variants.last(),
                quantity=30,
            ),
        ]
    )

    variables = {
        "filter": {
            "stocks": {"quantity": quantity_input, "hotelIds": hotel_pks}
        },
        "channel": channel_USD.slug,
    }
    response = staff_api_client.post_graphql(
        query_rooms_with_filter, variables, check_no_permissions=False
    )
    content = get_graphql_content(response)
    rooms_data = content["data"]["rooms"]["edges"]

    room_ids = {
        graphene.Node.to_global_id("Room", rooms[index].pk)
        for index in indexes_of_rooms_in_result
    }

    assert len(rooms_data) == count
    assert {node["node"]["id"] for node in rooms_data} == room_ids


def test_query_rooms_with_filter_ids(
    api_client, room_list, query_rooms_with_filter, channel_USD
):
    # given
    room_ids = [
        graphene.Node.to_global_id("Room", room.id) for room in room_list
    ][:2]
    variables = {
        "filter": {"ids": room_ids},
        "channel": channel_USD.slug,
    }

    # when
    response = api_client.post_graphql(query_rooms_with_filter, variables)

    # then
    content = get_graphql_content(response)
    rooms_data = content["data"]["rooms"]["edges"]

    assert len(rooms_data) == 2
    assert [node["node"]["id"] for node in rooms_data] == room_ids


def test_query_room_image_by_id(user_api_client, room_with_image, channel_USD):
    image = room_with_image.images.first()
    query = """
    query roomImageById($imageId: ID!, $roomId: ID!, $channel: String) {
        room(id: $roomId, channel: $channel) {
            imageById(id: $imageId) {
                id
                url
            }
        }
    }
    """
    variables = {
        "roomId": graphene.Node.to_global_id("Room", room_with_image.pk),
        "imageId": graphene.Node.to_global_id("RoomImage", image.pk),
        "channel": channel_USD.slug,
    }
    response = user_api_client.post_graphql(query, variables)
    data = get_graphql_content(response)
    assert data["data"]["room"]["imageById"]["id"]
    assert data["data"]["room"]["imageById"]["url"]


def test_room_with_collections(
    staff_api_client, room, published_collection, permission_manage_rooms
):
    query = """
        query getRoom($roomID: ID!) {
            room(id: $roomID) {
                collections {
                    name
                }
            }
        }
        """
    room.collections.add(published_collection)
    room.save()
    room_id = graphene.Node.to_global_id("Room", room.id)

    variables = {"roomID": room_id}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["room"]
    assert data["collections"][0]["name"] == published_collection.name
    assert len(data["collections"]) == 1


def test_filter_rooms_by_wrong_attributes(user_api_client, room, channel_USD):
    room_attr = room.room_type.room_attributes.get(slug="color")
    attr_value = (
        room.room_type.variant_attributes.get(slug="size").values.first().id
    )
    query = """
    query ($channel: String){
        rooms(
            filter: {attributes: {slug: "%(slug)s", value: "%(value)s"}},
            first: 1,
            channel: $channel
        ) {
            edges {
                node {
                    name
                }
            }
        }
    }
    """ % {
        "slug": room_attr.slug,
        "value": attr_value,
    }

    variables = {"channel": channel_USD.slug}
    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    rooms = content["data"]["rooms"]["edges"]

    assert rooms == []


SORT_ROOMS_QUERY = """
    query ($channel:String) {
        rooms (
            sortBy: %(sort_by_room_order)s, first: 2, channel: $channel
        ) {
            edges {
                node {
                    name
                    roomType{
                        name
                    }
                    pricing {
                        priceRangeUndiscounted {
                            start {
                                gross {
                                    amount
                                }
                            }
                        }
                        priceRange {
                            start {
                                gross {
                                    amount
                                }
                            }
                        }
                    }
                    updatedAt
                }
            }
        }
    }
"""


def test_sort_rooms(user_api_client, room, channel_USD):
    room.updated_at = datetime.utcnow()
    room.save()

    room.pk = None
    room.slug = "second-room"
    room.updated_at = datetime.utcnow()
    room.save()
    RoomChannelListing.objects.create(
        room=room,
        channel=channel_USD,
        is_published=True,
        visible_in_listings=True,
    )
    variant = RoomVariant.objects.create(room=room, sku="1234")
    RoomVariantChannelListing.objects.create(
        variant=variant,
        channel=channel_USD,
        price_amount=Decimal(20),
        cost_price_amount=Decimal(2),
        currency=channel_USD.currency_code,
    )

    variables = {"channel": channel_USD.slug}
    query = SORT_ROOMS_QUERY

    # Test sorting by PRICE, ascending
    sort_by = f'{{field: PRICE, direction: ASC, channel: "{channel_USD.slug}"}}'
    asc_price_query = query % {"sort_by_room_order": sort_by}
    response = user_api_client.post_graphql(asc_price_query, variables)
    content = get_graphql_content(response)
    edges = content["data"]["rooms"]["edges"]
    price1 = edges[0]["node"]["pricing"]["priceRangeUndiscounted"]["start"]["gross"][
        "amount"
    ]
    price2 = edges[1]["node"]["pricing"]["priceRangeUndiscounted"]["start"]["gross"][
        "amount"
    ]
    assert price1 < price2

    # Test sorting by PRICE, descending
    sort_by = f'{{field: PRICE, direction:DESC, channel: "{channel_USD.slug}"}}'
    desc_price_query = query % {"sort_by_room_order": sort_by}
    response = user_api_client.post_graphql(desc_price_query, variables)
    content = get_graphql_content(response)
    edges = content["data"]["rooms"]["edges"]
    price1 = edges[0]["node"]["pricing"]["priceRangeUndiscounted"]["start"]["gross"][
        "amount"
    ]
    price2 = edges[1]["node"]["pricing"]["priceRangeUndiscounted"]["start"]["gross"][
        "amount"
    ]
    assert price1 > price2

    # Test sorting by MINIMAL_PRICE, ascending
    sort_by = f'{{field: MINIMAL_PRICE, direction:ASC, channel: "{channel_USD.slug}"}}'
    asc_price_query = query % {"sort_by_room_order": sort_by}
    response = user_api_client.post_graphql(asc_price_query, variables)
    content = get_graphql_content(response)
    edges = content["data"]["rooms"]["edges"]
    price1 = edges[0]["node"]["pricing"]["priceRange"]["start"]["gross"]["amount"]
    price2 = edges[1]["node"]["pricing"]["priceRange"]["start"]["gross"]["amount"]
    assert price1 < price2

    # Test sorting by MINIMAL_PRICE, descending
    sort_by = f'{{field: MINIMAL_PRICE, direction:DESC, channel: "{channel_USD.slug}"}}'
    desc_price_query = query % {"sort_by_room_order": sort_by}
    response = user_api_client.post_graphql(desc_price_query, variables)
    content = get_graphql_content(response)
    edges = content["data"]["rooms"]["edges"]
    price1 = edges[0]["node"]["pricing"]["priceRange"]["start"]["gross"]["amount"]
    price2 = edges[1]["node"]["pricing"]["priceRange"]["start"]["gross"]["amount"]
    assert price1 > price2

    # Test sorting by DATE, ascending
    asc_date_query = query % {"sort_by_room_order": "{field: DATE, direction:ASC}"}
    response = user_api_client.post_graphql(asc_date_query, variables)
    content = get_graphql_content(response)
    date_0 = content["data"]["rooms"]["edges"][0]["node"]["updatedAt"]
    date_1 = content["data"]["rooms"]["edges"][1]["node"]["updatedAt"]
    assert parse_datetime(date_0) < parse_datetime(date_1)

    # Test sorting by DATE, descending
    desc_date_query = query % {"sort_by_room_order": "{field: DATE, direction:DESC}"}
    response = user_api_client.post_graphql(desc_date_query, variables)
    content = get_graphql_content(response)
    date_0 = content["data"]["rooms"]["edges"][0]["node"]["updatedAt"]
    date_1 = content["data"]["rooms"]["edges"][1]["node"]["updatedAt"]
    assert parse_datetime(date_0) > parse_datetime(date_1)


def test_sort_rooms_room_type_name(
    user_api_client, room, room_with_default_variant, channel_USD
):
    variables = {"channel": channel_USD.slug}

    # Test sorting by TYPE, ascending
    asc_published_query = SORT_ROOMS_QUERY % {
        "sort_by_room_order": "{field: TYPE, direction:ASC}"
    }
    response = user_api_client.post_graphql(asc_published_query, variables)
    content = get_graphql_content(response)
    edges = content["data"]["rooms"]["edges"]
    room_type_name_0 = edges[0]["node"]["roomType"]["name"]
    room_type_name_1 = edges[1]["node"]["roomType"]["name"]
    assert room_type_name_0 < room_type_name_1

    # Test sorting by PUBLISHED, descending
    desc_published_query = SORT_ROOMS_QUERY % {
        "sort_by_room_order": "{field: TYPE, direction:DESC}"
    }
    response = user_api_client.post_graphql(desc_published_query, variables)
    content = get_graphql_content(response)
    room_type_name_0 = edges[0]["node"]["roomType"]["name"]
    room_type_name_1 = edges[1]["node"]["roomType"]["name"]
    assert room_type_name_0 < room_type_name_1


QUERY_ROOM_TYPE = """
    query ($id: ID!){
        roomType(
            id: $id,
        ) {
            id
            name
            weight {
                unit
                value
            }
        }
    }
    """


def test_room_type_query_by_id_weight_returned_in_default_unit(
    user_api_client, room_type, site_settings
):
    # given
    room_type.weight = Weight(kg=10)
    room_type.save(update_fields=["weight"])

    site_settings.default_weight_unit = WeightUnits.OUNCE
    site_settings.save(update_fields=["default_weight_unit"])

    variables = {"id": graphene.Node.to_global_id("RoomType", room_type.pk)}

    # when
    response = user_api_client.post_graphql(QUERY_ROOM_TYPE, variables=variables)

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["roomType"]
    assert room_data is not None
    assert room_data["name"] == room_type.name
    assert room_data["weight"]["value"] == 352.73999999999995
    assert room_data["weight"]["unit"] == WeightUnits.OUNCE.upper()


CREATE_ROOM_MUTATION = """
       mutation createRoom(
           $input: RoomCreateInput!
       ) {
                roomCreate(
                    input: $input) {
                        room {
                            category {
                                name
                            }
                            descriptionJson
                            chargeTaxes
                            taxType {
                                taxCode
                                description
                            }
                            name
                            slug
                            rating
                            roomType {
                                name
                            }
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
                          roomErrors {
                            field
                            code
                            message
                            attributes
                          }
                        }
                      }
"""


def test_create_room(
    staff_api_client,
    room_type,
    category,
    size_attribute,
    description_json,
    permission_manage_rooms,
    monkeypatch,
):
    query = CREATE_ROOM_MUTATION

    description_json = json.dumps(description_json)

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_name = "test name"
    room_slug = "room-test-slug"
    room_charge_taxes = True
    room_tax_rate = "STANDARD"

    # Mock tax interface with fake response from tax gateway
    monkeypatch.setattr(
        PluginsManager,
        "get_tax_code_from_object_meta",
        lambda self, x: TaxType(description="", code=room_tax_rate),
    )

    # Default attribute defined in room_type fixture
    color_attr = room_type.room_attributes.get(name="Color")
    color_value_slug = color_attr.values.first().slug
    color_attr_id = graphene.Node.to_global_id("Attribute", color_attr.id)

    # Add second attribute
    room_type.room_attributes.add(size_attribute)
    size_attr_id = graphene.Node.to_global_id("Attribute", size_attribute.id)
    non_existent_attr_value = "The cake is a lie"

    # test creating root room
    variables = {
        "input": {
            "roomType": room_type_id,
            "category": category_id,
            "name": room_name,
            "slug": room_slug,
            "descriptionJson": description_json,
            "chargeTaxes": room_charge_taxes,
            "taxCode": room_tax_rate,
            "attributes": [
                {"id": color_attr_id, "values": [color_value_slug]},
                {"id": size_attr_id, "values": [non_existent_attr_value]},
            ],
        }
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    assert data["roomErrors"] == []
    assert data["room"]["name"] == room_name
    assert data["room"]["slug"] == room_slug
    assert data["room"]["descriptionJson"] == description_json
    assert data["room"]["chargeTaxes"] == room_charge_taxes
    assert data["room"]["taxType"]["taxCode"] == room_tax_rate
    assert data["room"]["roomType"]["name"] == room_type.name
    assert data["room"]["category"]["name"] == category.name
    values = (
        data["room"]["attributes"][0]["values"][0]["slug"],
        data["room"]["attributes"][1]["values"][0]["slug"],
    )
    assert slugify(non_existent_attr_value) in values
    assert color_value_slug in values


@freeze_time("2020-03-18 12:00:00")
def test_create_room_with_rating(
    staff_api_client,
    room_type,
    category,
    permission_manage_rooms,
    settings,
):
    query = CREATE_ROOM_MUTATION

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_name = "test name"
    room_slug = "room-test-slug"
    expected_rating = 4.57

    variables = {
        "input": {
            "roomType": room_type_id,
            "category": category_id,
            "name": room_name,
            "slug": room_slug,
            "rating": expected_rating,
        }
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    assert data["roomErrors"] == []
    assert data["room"]["rating"] == expected_rating
    assert Room.objects.get().rating == expected_rating


def test_create_room_with_file_attribute(
    staff_api_client,
    room_type,
    category,
    file_attribute,
    color_attribute,
    permission_manage_rooms,
    settings,
):
    query = CREATE_ROOM_MUTATION

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_name = "test name"
    room_slug = "room-test-slug"

    values_count = file_attribute.values.count()

    # Add second attribute
    room_type.room_attributes.add(file_attribute)
    file_attr_id = graphene.Node.to_global_id("Attribute", file_attribute.id)
    existing_value = file_attribute.values.first()

    # test creating root room
    variables = {
        "input": {
            "roomType": room_type_id,
            "category": category_id,
            "name": room_name,
            "slug": room_slug,
            "attributes": [{"id": file_attr_id, "file": existing_value.file_url}],
        }
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    assert data["roomErrors"] == []
    assert data["room"]["name"] == room_name
    assert data["room"]["slug"] == room_slug
    assert data["room"]["roomType"]["name"] == room_type.name
    assert data["room"]["category"]["name"] == category.name
    assert len(data["room"]["attributes"]) == 2
    expected_attributes_data = [
        {"attribute": {"slug": color_attribute.slug}, "values": []},
        {
            "attribute": {"slug": file_attribute.slug},
            "values": [
                {
                    "name": existing_value.name,
                    "slug": f"{existing_value.slug}-2",
                    "file": {"url": existing_value.file_url, "contentType": None},
                }
            ],
        },
    ]
    for attr_data in data["room"]["attributes"]:
        assert attr_data in expected_attributes_data

    file_attribute.refresh_from_db()
    assert file_attribute.values.count() == values_count + 1


def test_create_room_with_file_attribute_new_attribute_value(
    staff_api_client,
    room_type,
    category,
    file_attribute,
    color_attribute,
    permission_manage_rooms,
    settings,
):
    query = CREATE_ROOM_MUTATION

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_name = "test name"
    room_slug = "room-test-slug"

    values_count = file_attribute.values.count()

    # Add second attribute
    room_type.room_attributes.add(file_attribute)
    file_attr_id = graphene.Node.to_global_id("Attribute", file_attribute.id)
    non_existing_value = "new_test.jpg"

    # test creating root room
    variables = {
        "input": {
            "roomType": room_type_id,
            "category": category_id,
            "name": room_name,
            "slug": room_slug,
            "attributes": [{"id": file_attr_id, "file": non_existing_value}],
        }
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    assert data["roomErrors"] == []
    assert data["room"]["name"] == room_name
    assert data["room"]["slug"] == room_slug
    assert data["room"]["roomType"]["name"] == room_type.name
    assert data["room"]["category"]["name"] == category.name
    assert len(data["room"]["attributes"]) == 2
    expected_attributes_data = [
        {"attribute": {"slug": color_attribute.slug}, "values": []},
        {
            "attribute": {"slug": file_attribute.slug},
            "values": [
                {
                    "name": non_existing_value,
                    "slug": slugify(non_existing_value, allow_unicode=True),
                    "file": {
                        "url": "http://testserver/media/" + non_existing_value,
                        "contentType": None,
                    },
                }
            ],
        },
    ]
    for attr_data in data["room"]["attributes"]:
        assert attr_data in expected_attributes_data

    file_attribute.refresh_from_db()
    assert file_attribute.values.count() == values_count + 1


def test_create_room_with_file_attribute_not_required_no_file_url_given(
    staff_api_client,
    room_type,
    category,
    file_attribute,
    color_attribute,
    permission_manage_rooms,
    settings,
):
    query = CREATE_ROOM_MUTATION

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_name = "test name"
    room_slug = "room-test-slug"

    file_attribute.value_required = False
    file_attribute.save(update_fields=["value_required"])

    # Add second attribute
    room_type.room_attributes.add(file_attribute)
    file_attr_id = graphene.Node.to_global_id("Attribute", file_attribute.id)

    # test creating root room
    variables = {
        "input": {
            "roomType": room_type_id,
            "category": category_id,
            "name": room_name,
            "slug": room_slug,
            "attributes": [{"id": file_attr_id, "values": ["test.txt"]}],
        }
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    assert data["roomErrors"] == []
    assert data["room"]["name"] == room_name
    assert data["room"]["slug"] == room_slug
    assert data["room"]["roomType"]["name"] == room_type.name
    assert data["room"]["category"]["name"] == category.name
    assert len(data["room"]["attributes"]) == 2
    expected_attributes_data = [
        {"attribute": {"slug": color_attribute.slug}, "values": []},
        {"attribute": {"slug": file_attribute.slug}, "values": []},
    ]
    for attr_data in data["room"]["attributes"]:
        assert attr_data in expected_attributes_data

    file_attribute.refresh_from_db()


def test_create_room_with_file_attribute_required_no_file_url_given(
    staff_api_client,
    room_type,
    category,
    file_attribute,
    color_attribute,
    permission_manage_rooms,
    settings,
):
    query = CREATE_ROOM_MUTATION

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_name = "test name"
    room_slug = "room-test-slug"

    file_attribute.value_required = True
    file_attribute.save(update_fields=["value_required"])

    # Add second attribute
    room_type.room_attributes.add(file_attribute)
    file_attr_id = graphene.Node.to_global_id("Attribute", file_attribute.id)

    # test creating root room
    variables = {
        "input": {
            "roomType": room_type_id,
            "category": category_id,
            "name": room_name,
            "slug": room_slug,
            "attributes": [{"id": file_attr_id, "values": ["test.txt"]}],
        }
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    errors = data["roomErrors"]
    assert not data["room"]
    assert len(errors) == 1
    assert errors[0]["code"] == RoomErrorCode.REQUIRED.name
    assert errors[0]["field"] == "attributes"
    assert errors[0]["attributes"] == [
        graphene.Node.to_global_id("Attribute", file_attribute.pk)
    ]


def test_create_room_no_values_given(
    staff_api_client,
    room_type,
    category,
    permission_manage_rooms,
):
    query = CREATE_ROOM_MUTATION

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_name = "test name"
    room_slug = "room-test-slug"

    # Default attribute defined in room_type fixture
    color_attr = room_type.room_attributes.get(name="Color")
    color_attr_id = graphene.Node.to_global_id("Attribute", color_attr.id)

    # test creating root room
    variables = {
        "input": {
            "roomType": room_type_id,
            "category": category_id,
            "name": room_name,
            "slug": room_slug,
            "attributes": [{"id": color_attr_id, "file": "test.jpg"}],
        }
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    assert data["roomErrors"] == []
    assert data["room"]["name"] == room_name
    assert data["room"]["slug"] == room_slug
    assert data["room"]["roomType"]["name"] == room_type.name
    assert data["room"]["category"]["name"] == category.name
    assert len(data["room"]["attributes"]) == 1
    assert data["room"]["attributes"][0]["values"] == []


ROOM_VARIANT_SET_DEFAULT_MUTATION = """
    mutation Prod($roomId: ID!, $variantId: ID!) {
        roomVariantSetDefault(roomId: $roomId, variantId: $variantId) {
            room {
                defaultVariant {
                    id
                }
            }
            roomErrors {
                code
                field
            }
        }
    }
"""


REORDER_ROOM_VARIANTS_MUTATION = """
    mutation RoomVariantReorder($room: ID!, $moves: [ReorderInput]!) {
        roomVariantReorder(roomId: $room, moves: $moves) {
            roomErrors {
                code
                field
            }
            room {
                id
            }
        }
    }
"""


def test_room_variant_set_default(
    staff_api_client, permission_manage_rooms, room_with_two_variants
):
    assert not room_with_two_variants.default_variant

    first_variant = room_with_two_variants.variants.first()
    first_variant_id = graphene.Node.to_global_id("RoomVariant", first_variant.pk)

    variables = {
        "roomId": graphene.Node.to_global_id(
            "Room", room_with_two_variants.pk
        ),
        "variantId": first_variant_id,
    }

    response = staff_api_client.post_graphql(
        ROOM_VARIANT_SET_DEFAULT_MUTATION,
        variables,
        permissions=[permission_manage_rooms],
    )
    room_with_two_variants.refresh_from_db()
    assert room_with_two_variants.default_variant == first_variant
    content = get_graphql_content(response)
    data = content["data"]["roomVariantSetDefault"]
    assert not data["roomErrors"]
    assert data["room"]["defaultVariant"]["id"] == first_variant_id


def test_room_variant_set_default_invalid_id(
    staff_api_client, permission_manage_rooms, room_with_two_variants
):
    assert not room_with_two_variants.default_variant

    first_variant = room_with_two_variants.variants.first()

    variables = {
        "roomId": graphene.Node.to_global_id(
            "Room", room_with_two_variants.pk
        ),
        "variantId": graphene.Node.to_global_id("Room", first_variant.pk),
    }

    response = staff_api_client.post_graphql(
        ROOM_VARIANT_SET_DEFAULT_MUTATION,
        variables,
        permissions=[permission_manage_rooms],
    )
    room_with_two_variants.refresh_from_db()
    assert not room_with_two_variants.default_variant
    content = get_graphql_content(response)
    data = content["data"]["roomVariantSetDefault"]
    assert data["roomErrors"][0]["code"] == RoomErrorCode.INVALID.name
    assert data["roomErrors"][0]["field"] == "variantId"


def test_room_variant_set_default_not_rooms_variant(
    staff_api_client,
    permission_manage_rooms,
    room_with_two_variants,
    room_with_single_variant,
):
    assert not room_with_two_variants.default_variant

    foreign_variant = room_with_single_variant.variants.first()

    variables = {
        "roomId": graphene.Node.to_global_id(
            "Room", room_with_two_variants.pk
        ),
        "variantId": graphene.Node.to_global_id("RoomVariant", foreign_variant.pk),
    }

    response = staff_api_client.post_graphql(
        ROOM_VARIANT_SET_DEFAULT_MUTATION,
        variables,
        permissions=[permission_manage_rooms],
    )
    room_with_two_variants.refresh_from_db()
    assert not room_with_two_variants.default_variant
    content = get_graphql_content(response)
    data = content["data"]["roomVariantSetDefault"]
    assert (
        data["roomErrors"][0]["code"] == RoomErrorCode.NOT_ROOMS_VARIANT.name
    )
    assert data["roomErrors"][0]["field"] == "variantId"


def test_reorder_variants(
    staff_api_client,
    room_with_two_variants,
    permission_manage_rooms,
):
    default_variants = room_with_two_variants.variants.all()
    new_variants = [default_variants[1], default_variants[0]]

    variables = {
        "room": graphene.Node.to_global_id("Room", room_with_two_variants.pk),
        "moves": [
            {
                "id": graphene.Node.to_global_id("RoomVariant", variant.pk),
                "sortOrder": _order + 1,
            }
            for _order, variant in enumerate(new_variants)
        ],
    }

    response = staff_api_client.post_graphql(
        REORDER_ROOM_VARIANTS_MUTATION,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantReorder"]
    assert not data["roomErrors"]
    assert list(room_with_two_variants.variants.all()) == new_variants


def test_reorder_variants_invalid_variants(
    staff_api_client,
    room,
    room_with_two_variants,
    permission_manage_rooms,
):
    default_variants = room_with_two_variants.variants.all()
    new_variants = [room.variants.first(), default_variants[1]]

    variables = {
        "room": graphene.Node.to_global_id("Room", room_with_two_variants.pk),
        "moves": [
            {
                "id": graphene.Node.to_global_id("RoomVariant", variant.pk),
                "sortOrder": _order + 1,
            }
            for _order, variant in enumerate(new_variants)
        ],
    }

    response = staff_api_client.post_graphql(
        REORDER_ROOM_VARIANTS_MUTATION,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantReorder"]
    assert data["roomErrors"][0]["field"] == "moves"
    assert data["roomErrors"][0]["code"] == RoomErrorCode.NOT_FOUND.name


@pytest.mark.parametrize("input_slug", ["", None])
def test_create_room_no_slug_in_input(
    staff_api_client,
    room_type,
    category,
    size_attribute,
    description_json,
    permission_manage_rooms,
    monkeypatch,
    input_slug,
):
    query = CREATE_ROOM_MUTATION

    description_json = json.dumps(description_json)

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_name = "test name"
    room_tax_rate = "STANDARD"

    # Mock tax interface with fake response from tax gateway
    monkeypatch.setattr(
        PluginsManager,
        "get_tax_code_from_object_meta",
        lambda self, x: TaxType(description="", code=room_tax_rate),
    )

    # test creating root room
    variables = {
        "input": {
            "roomType": room_type_id,
            "category": category_id,
            "name": room_name,
            "slug": input_slug,
            "taxCode": room_tax_rate,
        }
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    assert data["roomErrors"] == []
    assert data["room"]["name"] == room_name
    assert data["room"]["slug"] == "test-name"
    assert data["room"]["taxType"]["taxCode"] == room_tax_rate
    assert data["room"]["roomType"]["name"] == room_type.name
    assert data["room"]["category"]["name"] == category.name


def test_create_room_no_category_id(
    staff_api_client,
    room_type,
    category,
    size_attribute,
    description_json,
    permission_manage_rooms,
    monkeypatch,
):
    query = CREATE_ROOM_MUTATION

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    room_name = "test name"
    room_tax_rate = "STANDARD"
    input_slug = "test-slug"

    # Mock tax interface with fake response from tax gateway
    monkeypatch.setattr(
        PluginsManager,
        "get_tax_code_from_object_meta",
        lambda self, x: TaxType(description="", code=room_tax_rate),
    )

    variables = {
        "input": {
            "roomType": room_type_id,
            "name": room_name,
            "slug": input_slug,
            "taxCode": room_tax_rate,
        }
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    assert data["roomErrors"] == []
    assert data["room"]["name"] == room_name
    assert data["room"]["slug"] == input_slug
    assert data["room"]["taxType"]["taxCode"] == room_tax_rate
    assert data["room"]["roomType"]["name"] == room_type.name
    assert data["room"]["category"] is None


def test_create_room_with_negative_weight(
    staff_api_client,
    room_type,
    category,
    description_json,
    permission_manage_rooms,
):
    query = CREATE_ROOM_MUTATION

    description_json = json.dumps(description_json)

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_name = "test name"

    variables = {
        "input": {
            "roomType": room_type_id,
            "category": category_id,
            "name": room_name,
            "weight": -1,
        }
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    error = data["roomErrors"][0]
    assert error["field"] == "weight"
    assert error["code"] == RoomErrorCode.INVALID.name


def test_create_room_with_unicode_in_slug_and_name(
    staff_api_client,
    room_type,
    category,
    description_json,
    permission_manage_rooms,
):
    query = CREATE_ROOM_MUTATION

    description_json = json.dumps(description_json)

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_name = "わたし-わ にっぽん です"
    slug = "わたし-わ-にっぽん-です-2"

    variables = {
        "input": {
            "roomType": room_type_id,
            "category": category_id,
            "name": room_name,
            "slug": slug,
        }
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    error = data["roomErrors"]
    assert not error
    assert data["room"]["name"] == room_name
    assert data["room"]["slug"] == slug


def test_create_room_invalid_room_attributes(
    staff_api_client,
    room_type,
    category,
    size_attribute,
    weight_attribute,
    description_json,
    permission_manage_rooms,
    settings,
    monkeypatch,
):
    query = CREATE_ROOM_MUTATION

    description_json = json.dumps(description_json)

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_name = "test name"
    room_slug = "room-test-slug"
    room_charge_taxes = True
    room_tax_rate = "STANDARD"

    # Mock tax interface with fake response from tax gateway
    monkeypatch.setattr(
        PluginsManager,
        "get_tax_code_from_object_meta",
        lambda self, x: TaxType(description="", code=room_tax_rate),
    )

    # Default attribute defined in room_type fixture
    color_attr = room_type.room_attributes.get(name="Color")
    color_value_slug = color_attr.values.first().slug
    color_attr_id = graphene.Node.to_global_id("Attribute", color_attr.id)

    # Add second attribute
    room_type.room_attributes.add(size_attribute)
    size_attr_id = graphene.Node.to_global_id("Attribute", size_attribute.id)
    non_existent_attr_value = "The cake is a lie"

    # Add third attribute
    room_type.room_attributes.add(weight_attribute)
    weight_attr_id = graphene.Node.to_global_id("Attribute", weight_attribute.id)

    # test creating root room
    variables = {
        "input": {
            "roomType": room_type_id,
            "category": category_id,
            "name": room_name,
            "slug": room_slug,
            "descriptionJson": description_json,
            "chargeTaxes": room_charge_taxes,
            "taxCode": room_tax_rate,
            "attributes": [
                {"id": color_attr_id, "values": [" "]},
                {"id": weight_attr_id, "values": [None]},
                {
                    "id": size_attr_id,
                    "values": [non_existent_attr_value, color_value_slug],
                },
            ],
        }
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    errors = data["roomErrors"]

    assert not data["room"]
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


QUERY_CREATE_ROOM_WITHOUT_VARIANTS = """
    mutation createRoom(
        $roomTypeId: ID!,
        $categoryId: ID!
        $name: String!)
    {
        roomCreate(
            input: {
                category: $categoryId,
                roomType: $roomTypeId,
                name: $name,
            })
        {
            room {
                id
                name
                slug
                rating
                category {
                    name
                }
                roomType {
                    name
                }
            }
            errors {
                message
                field
            }
        }
    }
    """


def test_create_room_without_variants(
    staff_api_client, room_type_without_variant, category, permission_manage_rooms
):
    query = QUERY_CREATE_ROOM_WITHOUT_VARIANTS

    room_type = room_type_without_variant
    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_name = "test name"
    room_slug = "test-name"

    variables = {
        "roomTypeId": room_type_id,
        "categoryId": category_id,
        "name": room_name,
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomCreate"]
    assert data["errors"] == []
    assert data["room"]["name"] == room_name
    assert data["room"]["slug"] == room_slug
    assert data["room"]["roomType"]["name"] == room_type.name
    assert data["room"]["category"]["name"] == category.name


def test_room_create_without_room_type(
    staff_api_client, category, permission_manage_rooms
):
    query = """
    mutation createRoom($categoryId: ID!) {
        roomCreate(input: {
                name: "Room",
                roomType: "",
                category: $categoryId}) {
            room {
                id
            }
            errors {
                message
                field
            }
        }
    }
    """

    category_id = graphene.Node.to_global_id("Category", category.id)
    response = staff_api_client.post_graphql(
        query, {"categoryId": category_id}, permissions=[permission_manage_rooms]
    )
    errors = get_graphql_content(response)["data"]["roomCreate"]["errors"]

    assert errors[0]["field"] == "roomType"
    assert errors[0]["message"] == "This field cannot be null."


def test_room_create_with_collections_webhook(
    staff_api_client,
    permission_manage_rooms,
    published_collection,
    room_type,
    category,
    monkeypatch,
):
    query = """
    mutation createRoom($roomTypeId: ID!, $collectionId: ID!, $categoryId: ID!) {
        roomCreate(input: {
                name: "Room",
                roomType: $roomTypeId,
                collections: [$collectionId],
                category: $categoryId
            }) {
            room {
                id,
                collections {
                    slug
                },
                category {
                    slug
                }
            }
            errors {
                message
                field
            }
        }
    }

    """

    def assert_room_has_collections(room):
        assert room.collections.count() > 0
        assert room.collections.first() == published_collection

    monkeypatch.setattr(
        "vanphong.plugins.manager.PluginsManager.room_created",
        lambda _, room: assert_room_has_collections(room),
    )

    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    category_id = graphene.Node.to_global_id("Category", category.pk)
    collection_id = graphene.Node.to_global_id("Collection", published_collection.pk)

    response = staff_api_client.post_graphql(
        query,
        {
            "roomTypeId": room_type_id,
            "categoryId": category_id,
            "collectionId": collection_id,
        },
        permissions=[permission_manage_rooms],
    )

    get_graphql_content(response)


MUTATION_UPDATE_ROOM = """
    mutation updateRoom($roomId: ID!, $input: RoomInput!) {
        roomUpdate(id: $roomId, input: $input) {
                room {
                    category {
                        name
                    }
                    rating
                    descriptionJson
                    chargeTaxes
                    variants {
                        name
                    }
                    taxType {
                        taxCode
                        description
                    }
                    name
                    slug
                    roomType {
                        name
                    }
                    attributes {
                        attribute {
                            id
                            name
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
                }
                roomErrors {
                    message
                    field
                    code
                }
            }
        }
"""


@patch("vanphong.plugins.manager.PluginsManager.room_updated")
def test_update_room(
    updated_webhook_mock,
    staff_api_client,
    category,
    non_default_category,
    room,
    other_description_json,
    permission_manage_rooms,
    monkeypatch,
    color_attribute,
):
    query = MUTATION_UPDATE_ROOM
    other_description_json = json.dumps(other_description_json)

    room_id = graphene.Node.to_global_id("Room", room.pk)
    category_id = graphene.Node.to_global_id("Category", non_default_category.pk)
    room_name = "updated name"
    room_slug = "updated-room"
    room_charge_taxes = True
    room_tax_rate = "STANDARD"

    # Mock tax interface with fake response from tax gateway
    monkeypatch.setattr(
        PluginsManager,
        "get_tax_code_from_object_meta",
        lambda self, x: TaxType(description="", code=room_tax_rate),
    )

    attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.pk)

    variables = {
        "roomId": room_id,
        "input": {
            "category": category_id,
            "name": room_name,
            "slug": room_slug,
            "descriptionJson": other_description_json,
            "chargeTaxes": room_charge_taxes,
            "taxCode": room_tax_rate,
            "attributes": [{"id": attribute_id, "values": ["Rainbow"]}],
        },
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomUpdate"]
    assert data["roomErrors"] == []
    assert data["room"]["name"] == room_name
    assert data["room"]["slug"] == room_slug
    assert data["room"]["descriptionJson"] == other_description_json
    assert data["room"]["chargeTaxes"] == room_charge_taxes
    assert data["room"]["taxType"]["taxCode"] == room_tax_rate
    assert not data["room"]["category"]["name"] == category.name

    attributes = data["room"]["attributes"]

    assert len(attributes) == 1
    assert len(attributes[0]["values"]) == 1

    assert attributes[0]["attribute"]["id"] == attribute_id
    assert attributes[0]["values"][0]["name"] == "Rainbow"
    assert attributes[0]["values"][0]["slug"] == "rainbow"

    updated_webhook_mock.assert_called_once_with(room)


@patch("vanphong.plugins.manager.PluginsManager.room_updated")
def test_update_room_with_file_attribute_value(
    updated_webhook_mock,
    staff_api_client,
    file_attribute,
    non_default_category,
    room,
    room_type,
    permission_manage_rooms,
    color_attribute,
):
    # given
    query = MUTATION_UPDATE_ROOM

    room_id = graphene.Node.to_global_id("Room", room.pk)

    attribute_id = graphene.Node.to_global_id("Attribute", file_attribute.pk)
    room_type.room_attributes.add(file_attribute)

    new_value = "new_file.json"

    variables = {
        "roomId": room_id,
        "input": {"attributes": [{"id": attribute_id, "file": new_value}]},
    }

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomUpdate"]
    assert data["roomErrors"] == []

    attributes = data["room"]["attributes"]

    assert len(attributes) == 2
    expected_file_att_data = {
        "attribute": {"id": attribute_id, "name": file_attribute.name},
        "values": [
            {
                "name": new_value,
                "slug": slugify(new_value),
                "file": {
                    "url": "http://testserver/media/" + new_value,
                    "contentType": None,
                },
            }
        ],
    }
    assert expected_file_att_data in attributes

    updated_webhook_mock.assert_called_once_with(room)


@patch("vanphong.plugins.manager.PluginsManager.room_updated")
def test_update_room_with_file_attribute_value_new_value_is_not_created(
    updated_webhook_mock,
    staff_api_client,
    file_attribute,
    room,
    room_type,
    permission_manage_rooms,
):
    # given
    query = MUTATION_UPDATE_ROOM

    room_id = graphene.Node.to_global_id("Room", room.pk)

    attribute_id = graphene.Node.to_global_id("Attribute", file_attribute.pk)
    room_type.room_attributes.add(file_attribute)
    existing_value = file_attribute.values.first()
    associate_attribute_values_to_instance(room, file_attribute, existing_value)

    variables = {
        "roomId": room_id,
        "input": {
            "attributes": [{"id": attribute_id, "file": existing_value.file_url}]
        },
    }

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomUpdate"]
    assert data["roomErrors"] == []

    attributes = data["room"]["attributes"]

    assert len(attributes) == 2
    expected_file_att_data = {
        "attribute": {"id": attribute_id, "name": file_attribute.name},
        "values": [
            {
                "name": existing_value.name,
                "slug": existing_value.slug,
                "file": {
                    "url": existing_value.file_url,
                    "contentType": existing_value.content_type,
                },
            }
        ],
    }
    assert expected_file_att_data in attributes

    updated_webhook_mock.assert_called_once_with(room)


@freeze_time("2020-03-18 12:00:00")
def test_update_room_rating(
    staff_api_client,
    room,
    permission_manage_rooms,
):
    query = MUTATION_UPDATE_ROOM

    room.rating = 5.5
    room.save(update_fields=["rating"])
    room_id = graphene.Node.to_global_id("Room", room.pk)
    expected_rating = 9.57
    variables = {"roomId": room_id, "input": {"rating": expected_rating}}

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomUpdate"]
    assert data["roomErrors"] == []
    assert data["room"]["rating"] == expected_rating
    room.refresh_from_db()
    assert room.rating == expected_rating


UPDATE_ROOM_SLUG_MUTATION = """
    mutation($id: ID!, $slug: String) {
        roomUpdate(
            id: $id
            input: {
                slug: $slug
            }
        ) {
            room{
                name
                slug
            }
            roomErrors {
                field
                message
                code
            }
        }
    }
"""


@pytest.mark.parametrize(
    "input_slug, expected_slug, error_message",
    [
        ("test-slug", "test-slug", None),
        ("", "", "Slug value cannot be blank."),
        (None, "", "Slug value cannot be blank."),
    ],
)
def test_update_room_slug(
    staff_api_client,
    room,
    permission_manage_rooms,
    input_slug,
    expected_slug,
    error_message,
):
    query = UPDATE_ROOM_SLUG_MUTATION
    old_slug = room.slug

    assert old_slug != input_slug

    node_id = graphene.Node.to_global_id("Room", room.id)
    variables = {"slug": input_slug, "id": node_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomUpdate"]
    errors = data["roomErrors"]
    if not error_message:
        assert not errors
        assert data["room"]["slug"] == expected_slug
    else:
        assert errors
        assert errors[0]["field"] == "slug"
        assert errors[0]["code"] == RoomErrorCode.REQUIRED.name


def test_update_room_slug_exists(
    staff_api_client, room, permission_manage_rooms
):
    query = UPDATE_ROOM_SLUG_MUTATION
    input_slug = "test-slug"

    second_room = Room.objects.get(pk=room.pk)
    second_room.pk = None
    second_room.slug = input_slug
    second_room.save()

    assert input_slug != room.slug

    node_id = graphene.Node.to_global_id("Room", room.id)
    variables = {"slug": input_slug, "id": node_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomUpdate"]
    errors = data["roomErrors"]
    assert errors
    assert errors[0]["field"] == "slug"
    assert errors[0]["code"] == RoomErrorCode.UNIQUE.name


@pytest.mark.parametrize(
    "input_slug, expected_slug, input_name, error_message, error_field",
    [
        ("test-slug", "test-slug", "New name", None, None),
        ("", "", "New name", "Slug value cannot be blank.", "slug"),
        (None, "", "New name", "Slug value cannot be blank.", "slug"),
        ("test-slug", "", None, "This field cannot be blank.", "name"),
        ("test-slug", "", "", "This field cannot be blank.", "name"),
        (None, None, None, "Slug value cannot be blank.", "slug"),
    ],
)
def test_update_room_slug_and_name(
    staff_api_client,
    room,
    permission_manage_rooms,
    input_slug,
    expected_slug,
    input_name,
    error_message,
    error_field,
):
    query = """
            mutation($id: ID!, $name: String, $slug: String) {
            roomUpdate(
                id: $id
                input: {
                    name: $name
                    slug: $slug
                }
            ) {
                room{
                    name
                    slug
                }
                roomErrors {
                    field
                    message
                    code
                }
            }
        }
    """

    old_name = room.name
    old_slug = room.slug

    assert input_slug != old_slug
    assert input_name != old_name

    node_id = graphene.Node.to_global_id("Room", room.id)
    variables = {"slug": input_slug, "name": input_name, "id": node_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    room.refresh_from_db()
    data = content["data"]["roomUpdate"]
    errors = data["roomErrors"]
    if not error_message:
        assert data["room"]["name"] == input_name == room.name
        assert data["room"]["slug"] == input_slug == room.slug
    else:
        assert errors
        assert errors[0]["field"] == error_field
        assert errors[0]["code"] == RoomErrorCode.REQUIRED.name


SET_ATTRIBUTES_TO_ROOM_QUERY = """
    mutation updateRoom($roomId: ID!, $attributes: [AttributeValueInput!]) {
      roomUpdate(id: $roomId, input: { attributes: $attributes }) {
        roomErrors {
          message
          field
          code
          attributes
        }
      }
    }
"""


def test_update_room_can_only_assign_multiple_values_to_valid_input_types(
    staff_api_client, room, permission_manage_rooms, color_attribute
):
    """Ensures you cannot assign multiple values to input types
    that are not multi-select. This also ensures multi-select types
    can be assigned multiple values as intended."""

    staff_api_client.user.user_permissions.add(permission_manage_rooms)

    multi_values_attr = Attribute.objects.create(
        name="multi", slug="multi-vals", input_type=AttributeInputType.MULTISELECT
    )
    multi_values_attr.room_types.add(room.room_type)
    multi_values_attr_id = graphene.Node.to_global_id("Attribute", multi_values_attr.id)

    color_attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.id)

    # Try to assign multiple values from an attribute that does not support such things
    variables = {
        "roomId": graphene.Node.to_global_id("Room", room.pk),
        "attributes": [{"id": color_attribute_id, "values": ["red", "blue"]}],
    }
    data = get_graphql_content(
        staff_api_client.post_graphql(SET_ATTRIBUTES_TO_ROOM_QUERY, variables)
    )["data"]["roomUpdate"]
    assert data["roomErrors"] == [
        {
            "field": "attributes",
            "code": RoomErrorCode.INVALID.name,
            "message": ANY,
            "attributes": [color_attribute_id],
        }
    ]

    # Try to assign multiple values from a valid attribute
    variables["attributes"] = [{"id": multi_values_attr_id, "values": ["a", "b"]}]
    data = get_graphql_content(
        staff_api_client.post_graphql(SET_ATTRIBUTES_TO_ROOM_QUERY, variables)
    )["data"]["roomUpdate"]
    assert not data["roomErrors"]


def test_update_room_with_existing_attribute_value(
    staff_api_client, room, permission_manage_rooms, color_attribute
):
    """Ensure assigning an existing value to a room doesn't create a new
    attribute value."""

    staff_api_client.user.user_permissions.add(permission_manage_rooms)

    expected_attribute_values_count = color_attribute.values.count()
    color_attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.id)
    color = color_attribute.values.only("name").first()

    # Try to assign multiple values from an attribute that does not support such things
    variables = {
        "roomId": graphene.Node.to_global_id("Room", room.pk),
        "attributes": [{"id": color_attribute_id, "values": [color.name]}],
    }

    data = get_graphql_content(
        staff_api_client.post_graphql(SET_ATTRIBUTES_TO_ROOM_QUERY, variables)
    )["data"]["roomUpdate"]
    assert not data["roomErrors"]

    assert (
        color_attribute.values.count() == expected_attribute_values_count
    ), "A new attribute value shouldn't have been created"


def test_update_room_without_supplying_required_room_attribute(
    staff_api_client, room, permission_manage_rooms, color_attribute
):
    """Ensure assigning an existing value to a room doesn't create a new
    attribute value."""

    staff_api_client.user.user_permissions.add(permission_manage_rooms)

    room_type = room.room_type
    color_attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.id)

    # Create and assign a new attribute requiring a value to be always supplied
    required_attribute = Attribute.objects.create(
        name="Required One", slug="required-one", value_required=True
    )
    room_type.room_attributes.add(required_attribute)
    required_attribute_id = graphene.Node.to_global_id(
        "Attribute", required_attribute.id
    )

    # Try to assign multiple values from an attribute that does not support such things
    variables = {
        "roomId": graphene.Node.to_global_id("Room", room.pk),
        "attributes": [{"id": color_attribute_id, "values": ["Blue"]}],
    }

    data = get_graphql_content(
        staff_api_client.post_graphql(SET_ATTRIBUTES_TO_ROOM_QUERY, variables)
    )["data"]["roomUpdate"]
    assert data["roomErrors"] == [
        {
            "field": "attributes",
            "code": RoomErrorCode.REQUIRED.name,
            "message": ANY,
            "attributes": [required_attribute_id],
        }
    ]


def test_update_room_with_non_existing_attribute(
    staff_api_client, room, permission_manage_rooms, color_attribute
):
    non_existent_attribute_pk = 0
    invalid_attribute_id = graphene.Node.to_global_id(
        "Attribute", non_existent_attribute_pk
    )

    """Ensure assigning an existing value to a room doesn't create a new
    attribute value."""

    staff_api_client.user.user_permissions.add(permission_manage_rooms)

    # Try to assign multiple values from an attribute that does not support such things
    variables = {
        "roomId": graphene.Node.to_global_id("Room", room.pk),
        "attributes": [{"id": invalid_attribute_id, "values": ["hello"]}],
    }

    data = get_graphql_content(
        staff_api_client.post_graphql(SET_ATTRIBUTES_TO_ROOM_QUERY, variables)
    )["data"]["roomUpdate"]
    assert data["roomErrors"] == [
        {
            "field": "attributes",
            "code": RoomErrorCode.NOT_FOUND.name,
            "message": ANY,
            "attributes": None,
        }
    ]


def test_update_room_with_no_attribute_slug_or_id(
    staff_api_client, room, permission_manage_rooms, color_attribute
):
    """Ensure only supplying values triggers a validation error."""

    staff_api_client.user.user_permissions.add(permission_manage_rooms)

    # Try to assign multiple values from an attribute that does not support such things
    variables = {
        "roomId": graphene.Node.to_global_id("Room", room.pk),
        "attributes": [{"values": ["Oopsie!"]}],
    }

    data = get_graphql_content(
        staff_api_client.post_graphql(SET_ATTRIBUTES_TO_ROOM_QUERY, variables)
    )["data"]["roomUpdate"]
    assert data["roomErrors"] == [
        {
            "field": "attributes",
            "code": RoomErrorCode.REQUIRED.name,
            "message": ANY,
            "attributes": None,
        }
    ]


def test_update_room_with_negative_weight(
    staff_api_client, room_with_default_variant, permission_manage_rooms, room
):
    query = """
        mutation updateRoom(
            $roomId: ID!,
            $weight: WeightScalar)
        {
            roomUpdate(
                id: $roomId,
                input: {
                    weight: $weight
                })
            {
                room {
                    id
                }
                roomErrors {
                    field
                    message
                    code
                }
            }
        }
    """
    room = room_with_default_variant
    room_id = graphene.Node.to_global_id("Room", room.pk)

    variables = {"roomId": room_id, "weight": -1}

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomUpdate"]
    error = data["roomErrors"][0]
    assert error["field"] == "weight"
    assert error["code"] == RoomErrorCode.INVALID.name


UPDATE_ROOM = """
    mutation updateRoom(
        $roomId: ID!,
        $input: RoomInput!)
    {
        roomUpdate(
            id: $roomId,
            input: $input)
        {
            room {
                id
                name
                slug
            }
            errors {
                message
                field
            }
        }
    }"""


def test_update_room_name(staff_api_client, permission_manage_rooms, room):
    query = UPDATE_ROOM

    room_slug = room.slug
    new_name = "example-room"
    assert new_name != room.name

    room_id = graphene.Node.to_global_id("Room", room.id)
    variables = {"roomId": room_id, "input": {"name": new_name}}

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    data = get_graphql_content(response)["data"]["roomUpdate"]
    assert data["room"]["name"] == new_name
    assert data["room"]["slug"] == room_slug


def test_update_room_slug_with_existing_value(
    staff_api_client, permission_manage_rooms, room
):
    query = UPDATE_ROOM
    second_room = Room.objects.get(pk=room.pk)
    second_room.id = None
    second_room.slug = "second-room"
    second_room.save()

    assert room.slug != second_room.slug

    room_id = graphene.Node.to_global_id("Room", room.id)
    variables = {"roomId": room_id, "input": {"slug": second_room.slug}}

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    data = get_graphql_content(response)["data"]["roomUpdate"]
    errors = data["errors"]
    assert errors
    assert errors[0]["field"] == "slug"
    assert errors[0]["message"] == "Room with this Slug already exists."


DELETE_ROOM_MUTATION = """
    mutation DeleteRoom($id: ID!) {
        roomDelete(id: $id) {
            room {
                name
                id
            }
            errors {
                field
                message
            }
            }
        }
"""


def test_delete_room(staff_api_client, room, permission_manage_rooms):
    query = DELETE_ROOM_MUTATION
    node_id = graphene.Node.to_global_id("Room", room.id)
    variables = {"id": node_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomDelete"]
    assert data["room"]["name"] == room.name
    with pytest.raises(room._meta.model.DoesNotExist):
        room.refresh_from_db()
    assert node_id == data["room"]["id"]


def test_delete_room_variant_in_draft_order(
    staff_api_client,
    room_with_two_variants,
    permission_manage_rooms,
    order_list,
    channel_USD,
):
    query = DELETE_ROOM_MUTATION
    room = room_with_two_variants

    not_draft_order = order_list[1]
    draft_order = order_list[0]
    draft_order.status = OrderStatus.DRAFT
    draft_order.save(update_fields=["status"])

    draft_order_lines_pks = []
    not_draft_order_lines_pks = []
    for variant in room.variants.all():
        variant_channel_listing = variant.channel_listings.get(channel=channel_USD)
        net = variant.get_price(room, [], channel_USD, variant_channel_listing, None)
        gross = Money(amount=net.amount, currency=net.currency)
        unit_price = TaxedMoney(net=net, gross=gross)
        quantity = 3
        total_price = unit_price * quantity

        order_line = OrderLine.objects.create(
            variant=variant,
            order=draft_order,
            room_name=str(variant.room),
            variant_name=str(variant),
            room_sku=variant.sku,
            is_shipping_required=variant.is_shipping_required(),
            unit_price=TaxedMoney(net=net, gross=gross),
            total_price=total_price,
            quantity=quantity,
        )
        draft_order_lines_pks.append(order_line.pk)

        order_line_not_draft = OrderLine.objects.create(
            variant=variant,
            order=not_draft_order,
            room_name=str(variant.room),
            variant_name=str(variant),
            room_sku=variant.sku,
            is_shipping_required=variant.is_shipping_required(),
            unit_price=TaxedMoney(net=net, gross=gross),
            total_price=total_price,
            quantity=quantity,
        )
        not_draft_order_lines_pks.append(order_line_not_draft.pk)

    node_id = graphene.Node.to_global_id("Room", room.id)
    variables = {"id": node_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomDelete"]
    assert data["room"]["name"] == room.name
    with pytest.raises(room._meta.model.DoesNotExist):
        room.refresh_from_db()
    assert node_id == data["room"]["id"]

    assert not OrderLine.objects.filter(pk__in=draft_order_lines_pks).exists()

    assert OrderLine.objects.filter(pk__in=not_draft_order_lines_pks).exists()


def test_room_type(user_api_client, room_type, channel_USD):
    query = """
    query ($channel: String){
        roomTypes(first: 20) {
            totalCount
            edges {
                node {
                    id
                    name
                    rooms(first: 1, channel: $channel) {
                        edges {
                            node {
                                id
                            }
                        }
                    }
                }
            }
        }
    }
    """
    variables = {"channel": channel_USD.slug}
    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    no_room_types = RoomType.objects.count()
    assert content["data"]["roomTypes"]["totalCount"] == no_room_types
    assert len(content["data"]["roomTypes"]["edges"]) == no_room_types


ROOM_TYPE_QUERY = """
    query getRoomType(
        $id: ID!, $variantSelection: VariantAttributeScope, $channel: String
    ) {
        roomType(id: $id) {
            name
            variantAttributes(variantSelection: $variantSelection) {
                slug
            }
            rooms(first: 20, channel:$channel) {
                totalCount
                edges {
                    node {
                        name
                    }
                }
            }
            taxRate
            taxType {
                taxCode
                description
            }
        }
    }
"""


def test_room_type_query(
    user_api_client,
    staff_api_client,
    room_type,
    file_attribute_with_file_input_type_without_values,
    room,
    permission_manage_rooms,
    monkeypatch,
    channel_USD,
):
    monkeypatch.setattr(
        PluginsManager,
        "get_tax_code_from_object_meta",
        lambda self, x: TaxType(code="123", description="Standard Taxes"),
    )

    query = ROOM_TYPE_QUERY

    no_rooms = Room.objects.count()
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    room_type.variant_attributes.add(
        file_attribute_with_file_input_type_without_values
    )
    variant_attributes_count = room_type.variant_attributes.count()

    variables = {
        "id": graphene.Node.to_global_id("RoomType", room_type.id),
        "channel": channel_USD.slug,
    }

    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]
    assert data["roomType"]["rooms"]["totalCount"] == no_rooms - 1

    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]
    assert data["roomType"]["rooms"]["totalCount"] == no_rooms
    assert data["roomType"]["taxType"]["taxCode"] == "123"
    assert data["roomType"]["taxType"]["description"] == "Standard Taxes"
    assert len(data["roomType"]["variantAttributes"]) == variant_attributes_count


@pytest.mark.parametrize(
    "variant_selection",
    [
        VariantAttributeScope.ALL.name,
        VariantAttributeScope.VARIANT_SELECTION.name,
        VariantAttributeScope.NOT_VARIANT_SELECTION.name,
    ],
)
def test_room_type_query_only_variant_selections_value_set(
    variant_selection,
    user_api_client,
    staff_api_client,
    room_type,
    file_attribute_with_file_input_type_without_values,
    author_page_attribute,
    room,
    permission_manage_rooms,
    monkeypatch,
    channel_USD,
):
    monkeypatch.setattr(
        PluginsManager,
        "get_tax_code_from_object_meta",
        lambda self, x: TaxType(code="123", description="Standard Taxes"),
    )
    query = ROOM_TYPE_QUERY

    no_rooms = Room.objects.count()
    RoomChannelListing.objects.filter(room=room, channel=channel_USD).update(
        is_published=False
    )

    room_type.variant_attributes.add(
        file_attribute_with_file_input_type_without_values, author_page_attribute
    )

    variables = {
        "id": graphene.Node.to_global_id("RoomType", room_type.id),
        "variantSelection": variant_selection,
        "channel": channel_USD.slug,
    }

    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]
    assert data["roomType"]["rooms"]["totalCount"] == no_rooms - 1

    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]
    assert data["roomType"]["rooms"]["totalCount"] == no_rooms
    assert data["roomType"]["taxType"]["taxCode"] == "123"
    assert data["roomType"]["taxType"]["description"] == "Standard Taxes"

    if variant_selection == VariantAttributeScope.VARIANT_SELECTION.name:
        assert (
            len(data["roomType"]["variantAttributes"])
            == room_type.variant_attributes.filter(
                input_type=AttributeInputType.DROPDOWN, type=AttributeType.ROOM_TYPE
            ).count()
        )
    elif variant_selection == VariantAttributeScope.NOT_VARIANT_SELECTION.name:
        assert (
            len(data["roomType"]["variantAttributes"])
            == room_type.variant_attributes.exclude(
                input_type=AttributeInputType.DROPDOWN, type=AttributeType.ROOM_TYPE
            ).count()
        )
    else:
        assert (
            len(data["roomType"]["variantAttributes"])
            == room_type.variant_attributes.count()
        )


ROOM_TYPE_CREATE_MUTATION = """
    mutation createRoomType(
        $name: String,
        $slug: String,
        $taxCode: String,
        $hasVariants: Boolean,
        $isShippingRequired: Boolean,
        $roomAttributes: [ID],
        $variantAttributes: [ID],
        $weight: WeightScalar) {
        roomTypeCreate(
            input: {
                name: $name,
                slug: $slug,
                taxCode: $taxCode,
                hasVariants: $hasVariants,
                isShippingRequired: $isShippingRequired,
                roomAttributes: $roomAttributes,
                variantAttributes: $variantAttributes,
                weight: $weight}) {
            roomType {
                name
                slug
                taxRate
                isShippingRequired
                hasVariants
                variantAttributes {
                    name
                    values {
                        name
                    }
                }
                roomAttributes {
                    name
                    values {
                        name
                    }
                }
            }
            roomErrors {
                field
                message
                code
                attributes
            }
        }

    }
"""


def test_room_type_create_mutation(
    staff_api_client,
    room_type,
    permission_manage_room_types_and_attributes,
    monkeypatch,
    setup_vatlayer,
):
    manager = PluginsManager(plugins=setup_vatlayer.PLUGINS)

    query = ROOM_TYPE_CREATE_MUTATION
    room_type_name = "test type"
    slug = "test-type"
    has_variants = True
    require_shipping = True
    room_attributes = room_type.room_attributes.all()
    room_attributes_ids = [
        graphene.Node.to_global_id("Attribute", att.id) for att in room_attributes
    ]
    variant_attributes = room_type.variant_attributes.all()
    variant_attributes_ids = [
        graphene.Node.to_global_id("Attribute", att.id) for att in variant_attributes
    ]

    variables = {
        "name": room_type_name,
        "slug": slug,
        "hasVariants": has_variants,
        "taxCode": "wine",
        "isShippingRequired": require_shipping,
        "roomAttributes": room_attributes_ids,
        "variantAttributes": variant_attributes_ids,
    }
    initial_count = RoomType.objects.count()
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)
    assert RoomType.objects.count() == initial_count + 1
    data = content["data"]["roomTypeCreate"]["roomType"]
    assert data["name"] == room_type_name
    assert data["slug"] == slug
    assert data["hasVariants"] == has_variants
    assert data["isShippingRequired"] == require_shipping

    pa = room_attributes[0]
    assert data["roomAttributes"][0]["name"] == pa.name
    pa_values = data["roomAttributes"][0]["values"]
    assert sorted([value["name"] for value in pa_values]) == sorted(
        [value.name for value in pa.values.all()]
    )

    va = variant_attributes[0]
    assert data["variantAttributes"][0]["name"] == va.name
    va_values = data["variantAttributes"][0]["values"]
    assert sorted([value["name"] for value in va_values]) == sorted(
        [value.name for value in va.values.all()]
    )

    new_instance = RoomType.objects.latest("pk")
    tax_code = manager.get_tax_code_from_object_meta(new_instance).code
    assert tax_code == "wine"


@pytest.mark.parametrize(
    "input_slug, expected_slug",
    (
        ("test-slug", "test-slug"),
        (None, "test-room-type"),
        ("", "test-room-type"),
        ("わたし-わ-にっぽん-です", "わたし-わ-にっぽん-です"),
    ),
)
def test_create_room_type_with_given_slug(
    staff_api_client,
    permission_manage_room_types_and_attributes,
    input_slug,
    expected_slug,
):
    query = ROOM_TYPE_CREATE_MUTATION
    name = "Test room type"
    variables = {"name": name, "slug": input_slug}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomTypeCreate"]
    assert not data["roomErrors"]
    assert data["roomType"]["slug"] == expected_slug


def test_create_room_type_with_unicode_in_name(
    staff_api_client, permission_manage_room_types_and_attributes
):
    query = ROOM_TYPE_CREATE_MUTATION
    name = "わたし わ にっぽん です"
    variables = {"name": name}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomTypeCreate"]
    assert not data["roomErrors"]
    assert data["roomType"]["name"] == name
    assert data["roomType"]["slug"] == "わたし-わ-にっぽん-です"


def test_create_room_type_create_with_negative_weight(
    staff_api_client, permission_manage_room_types_and_attributes
):
    query = ROOM_TYPE_CREATE_MUTATION
    name = "Test room type"
    variables = {"name": name, "weight": -1.1}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomTypeCreate"]
    error = data["roomErrors"][0]
    assert error["field"] == "weight"
    assert error["code"] == RoomErrorCode.INVALID.name


def test_room_type_create_mutation_not_valid_attributes(
    staff_api_client,
    room_type,
    permission_manage_room_types_and_attributes,
    monkeypatch,
    setup_vatlayer,
):
    # given
    query = ROOM_TYPE_CREATE_MUTATION
    room_type_name = "test type"
    slug = "test-type"
    has_variants = True
    require_shipping = True

    room_attributes = room_type.room_attributes.all()
    room_page_attribute = room_attributes.last()
    room_page_attribute.type = AttributeType.PAGE_TYPE
    room_page_attribute.save(update_fields=["type"])

    variant_attributes = room_type.variant_attributes.all()
    variant_page_attribute = variant_attributes.last()
    variant_page_attribute.type = AttributeType.PAGE_TYPE
    variant_page_attribute.save(update_fields=["type"])

    room_attributes_ids = [
        graphene.Node.to_global_id("Attribute", att.id) for att in room_attributes
    ]
    variant_attributes_ids = [
        graphene.Node.to_global_id("Attribute", att.id) for att in variant_attributes
    ]

    variables = {
        "name": room_type_name,
        "slug": slug,
        "hasVariants": has_variants,
        "taxCode": "wine",
        "isShippingRequired": require_shipping,
        "roomAttributes": room_attributes_ids,
        "variantAttributes": variant_attributes_ids,
    }
    initial_count = RoomType.objects.count()

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomTypeCreate"]
    errors = data["roomErrors"]

    assert len(errors) == 2
    expected_errors = [
        {
            "code": RoomErrorCode.INVALID.name,
            "field": "roomAttributes",
            "message": ANY,
            "attributes": [
                graphene.Node.to_global_id("Attribute", room_page_attribute.pk)
            ],
        },
        {
            "code": RoomErrorCode.INVALID.name,
            "field": "variantAttributes",
            "message": ANY,
            "attributes": [
                graphene.Node.to_global_id("Attribute", variant_page_attribute.pk)
            ],
        },
    ]
    for error in errors:
        assert error in expected_errors

    assert initial_count == RoomType.objects.count()


ROOM_TYPE_UPDATE_MUTATION = """
mutation updateRoomType(
    $id: ID!,
    $name: String!,
    $hasVariants: Boolean!,
    $isShippingRequired: Boolean!,
    $roomAttributes: [ID],
    ) {
        roomTypeUpdate(
        id: $id,
        input: {
            name: $name,
            hasVariants: $hasVariants,
            isShippingRequired: $isShippingRequired,
            roomAttributes: $roomAttributes
        }) {
            roomType {
                name
                slug
                isShippingRequired
                hasVariants
                variantAttributes {
                    id
                }
                roomAttributes {
                    id
                }
            }
            roomErrors {
                code
                field
                attributes
            }
            }
        }
"""


def test_room_type_update_mutation(
    staff_api_client, room_type, permission_manage_room_types_and_attributes
):
    query = ROOM_TYPE_UPDATE_MUTATION
    room_type_name = "test type updated"
    slug = room_type.slug
    has_variants = True
    require_shipping = False
    room_type_id = graphene.Node.to_global_id("RoomType", room_type.id)

    # Test scenario: remove all room attributes using [] as input
    # but do not change variant attributes
    room_attributes = []
    room_attributes_ids = [
        graphene.Node.to_global_id("Attribute", att.id) for att in room_attributes
    ]
    variant_attributes = room_type.variant_attributes.all()

    variables = {
        "id": room_type_id,
        "name": room_type_name,
        "hasVariants": has_variants,
        "isShippingRequired": require_shipping,
        "roomAttributes": room_attributes_ids,
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomTypeUpdate"]["roomType"]
    assert data["name"] == room_type_name
    assert data["slug"] == slug
    assert data["hasVariants"] == has_variants
    assert data["isShippingRequired"] == require_shipping
    assert not data["roomAttributes"]
    assert len(data["variantAttributes"]) == (variant_attributes.count())


def test_room_type_update_mutation_not_valid_attributes(
    staff_api_client,
    room_type,
    permission_manage_room_types_and_attributes,
    size_page_attribute,
):
    # given
    query = ROOM_TYPE_UPDATE_MUTATION
    room_type_name = "test type updated"
    has_variants = True
    require_shipping = False
    room_type_id = graphene.Node.to_global_id("RoomType", room_type.id)

    # Test scenario: adding page attribute raise error

    page_attribute_id = graphene.Node.to_global_id("Attribute", size_page_attribute.id)
    room_attributes_ids = [
        page_attribute_id,
        graphene.Node.to_global_id(
            "Attribute", room_type.room_attributes.first().pk
        ),
    ]

    variables = {
        "id": room_type_id,
        "name": room_type_name,
        "hasVariants": has_variants,
        "isShippingRequired": require_shipping,
        "roomAttributes": room_attributes_ids,
    }

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomTypeUpdate"]
    errors = data["roomErrors"]

    assert len(errors) == 1
    assert errors[0]["field"] == "roomAttributes"
    assert errors[0]["code"] == RoomErrorCode.INVALID.name
    assert errors[0]["attributes"] == [page_attribute_id]


UPDATE_ROOM_TYPE_SLUG_MUTATION = """
    mutation($id: ID!, $slug: String) {
        roomTypeUpdate(
            id: $id
            input: {
                slug: $slug
            }
        ) {
            roomType{
                name
                slug
            }
            roomErrors {
                field
                message
                code
            }
        }
    }
"""


@pytest.mark.parametrize(
    "input_slug, expected_slug, error_message",
    [
        ("test-slug", "test-slug", None),
        ("", "", "Slug value cannot be blank."),
        (None, "", "Slug value cannot be blank."),
    ],
)
def test_update_room_type_slug(
    staff_api_client,
    room_type,
    permission_manage_room_types_and_attributes,
    input_slug,
    expected_slug,
    error_message,
):
    query = UPDATE_ROOM_TYPE_SLUG_MUTATION
    old_slug = room_type.slug

    assert old_slug != input_slug

    node_id = graphene.Node.to_global_id("RoomType", room_type.id)
    variables = {"slug": input_slug, "id": node_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomTypeUpdate"]
    errors = data["roomErrors"]
    if not error_message:
        assert not errors
        assert data["roomType"]["slug"] == expected_slug
    else:
        assert errors
        assert errors[0]["field"] == "slug"
        assert errors[0]["code"] == RoomErrorCode.REQUIRED.name


def test_update_room_type_slug_exists(
    staff_api_client, room_type, permission_manage_room_types_and_attributes
):
    query = UPDATE_ROOM_TYPE_SLUG_MUTATION
    input_slug = "test-slug"

    second_room_type = RoomType.objects.get(pk=room_type.pk)
    second_room_type.pk = None
    second_room_type.slug = input_slug
    second_room_type.save()

    assert input_slug != room_type.slug

    node_id = graphene.Node.to_global_id("RoomType", room_type.id)
    variables = {"slug": input_slug, "id": node_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomTypeUpdate"]
    errors = data["roomErrors"]
    assert errors
    assert errors[0]["field"] == "slug"
    assert errors[0]["code"] == RoomErrorCode.UNIQUE.name


@pytest.mark.parametrize(
    "input_slug, expected_slug, input_name, error_message, error_field",
    [
        ("test-slug", "test-slug", "New name", None, None),
        ("", "", "New name", "Slug value cannot be blank.", "slug"),
        (None, "", "New name", "Slug value cannot be blank.", "slug"),
        ("test-slug", "", None, "This field cannot be blank.", "name"),
        ("test-slug", "", "", "This field cannot be blank.", "name"),
        (None, None, None, "Slug value cannot be blank.", "slug"),
    ],
)
def test_update_room_type_slug_and_name(
    staff_api_client,
    room_type,
    permission_manage_room_types_and_attributes,
    input_slug,
    expected_slug,
    input_name,
    error_message,
    error_field,
):
    query = """
            mutation($id: ID!, $name: String, $slug: String) {
            roomTypeUpdate(
                id: $id
                input: {
                    name: $name
                    slug: $slug
                }
            ) {
                roomType{
                    name
                    slug
                }
                roomErrors {
                    field
                    message
                    code
                }
            }
        }
    """

    old_name = room_type.name
    old_slug = room_type.slug

    assert input_slug != old_slug
    assert input_name != old_name

    node_id = graphene.Node.to_global_id("RoomType", room_type.id)
    variables = {"slug": input_slug, "name": input_name, "id": node_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)
    room_type.refresh_from_db()
    data = content["data"]["roomTypeUpdate"]
    errors = data["roomErrors"]
    if not error_message:
        assert data["roomType"]["name"] == input_name == room_type.name
        assert data["roomType"]["slug"] == input_slug == room_type.slug
    else:
        assert errors
        assert errors[0]["field"] == error_field
        assert errors[0]["code"] == RoomErrorCode.REQUIRED.name


def test_update_room_type_with_negative_weight(
    staff_api_client,
    room_type,
    permission_manage_room_types_and_attributes,
):
    query = """
        mutation($id: ID!, $weight: WeightScalar) {
            roomTypeUpdate(
                id: $id
                input: {
                    weight: $weight
                }
            ) {
                roomType{
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

    node_id = graphene.Node.to_global_id("RoomType", room_type.id)
    variables = {"id": node_id, "weight": "-1"}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)
    room_type.refresh_from_db()
    data = content["data"]["roomTypeUpdate"]
    error = data["roomErrors"][0]
    assert error["field"] == "weight"
    assert error["code"] == RoomErrorCode.INVALID.name


ROOM_TYPE_DELETE_MUTATION = """
    mutation deleteRoomType($id: ID!) {
        roomTypeDelete(id: $id) {
            roomType {
                name
            }
        }
    }
"""


def test_room_type_delete_mutation(
    staff_api_client, room_type, permission_manage_room_types_and_attributes
):
    query = ROOM_TYPE_DELETE_MUTATION
    variables = {"id": graphene.Node.to_global_id("RoomType", room_type.id)}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomTypeDelete"]
    assert data["roomType"]["name"] == room_type.name
    with pytest.raises(room_type._meta.model.DoesNotExist):
        room_type.refresh_from_db()


def test_room_type_delete_mutation_variants_in_draft_order(
    staff_api_client,
    permission_manage_room_types_and_attributes,
    room,
    order_list,
    channel_USD,
):
    query = ROOM_TYPE_DELETE_MUTATION
    room_type = room.room_type

    variant = room.variants.first()

    order_not_draft = order_list[-1]
    draft_order = order_list[1]
    draft_order.status = OrderStatus.DRAFT
    draft_order.save(update_fields=["status"])

    variant_channel_listing = variant.channel_listings.get(channel=channel_USD)
    net = variant.get_price(room, [], channel_USD, variant_channel_listing, None)
    gross = Money(amount=net.amount, currency=net.currency)
    quantity = 3
    unit_price = TaxedMoney(net=net, gross=gross)
    total_price = unit_price * quantity

    order_line_not_in_draft = OrderLine.objects.create(
        variant=variant,
        order=order_not_draft,
        room_name=str(variant.room),
        variant_name=str(variant),
        room_sku=variant.sku,
        is_shipping_required=variant.is_shipping_required(),
        unit_price=TaxedMoney(net=net, gross=gross),
        total_price=total_price,
        quantity=3,
    )

    order_line_in_draft = OrderLine.objects.create(
        variant=variant,
        order=draft_order,
        room_name=str(variant.room),
        variant_name=str(variant),
        room_sku=variant.sku,
        is_shipping_required=variant.is_shipping_required(),
        unit_price=TaxedMoney(net=net, gross=gross),
        total_price=total_price,
        quantity=3,
    )

    variables = {"id": graphene.Node.to_global_id("RoomType", room_type.id)}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomTypeDelete"]
    assert data["roomType"]["name"] == room_type.name
    with pytest.raises(room_type._meta.model.DoesNotExist):
        room_type.refresh_from_db()

    with pytest.raises(order_line_in_draft._meta.model.DoesNotExist):
        order_line_in_draft.refresh_from_db()

    assert OrderLine.objects.filter(pk=order_line_not_in_draft.pk).exists()


def test_room_image_create_mutation(
    monkeypatch, staff_api_client, room, permission_manage_rooms, media_root
):
    query = """
    mutation createRoomImage($image: Upload!, $room: ID!) {
        roomImageCreate(input: {image: $image, room: $room}) {
            image {
                id
            }
        }
    }
    """
    mock_create_thumbnails = Mock(return_value=None)
    monkeypatch.setattr(
        (
            "vanphong.graphql.room.mutations.rooms."
            "create_room_thumbnails.delay"
        ),
        mock_create_thumbnails,
    )

    image_file, image_name = create_image()
    variables = {
        "room": graphene.Node.to_global_id("Room", room.id),
        "image": image_name,
    }
    body = get_multipart_request_body(query, variables, image_file, image_name)
    response = staff_api_client.post_multipart(
        body, permissions=[permission_manage_rooms]
    )
    get_graphql_content(response)
    room.refresh_from_db()
    room_image = room.images.last()
    assert room_image.image.file

    # The image creation should have triggered a warm-up
    mock_create_thumbnails.assert_called_once_with(room_image.pk)


def test_room_image_create_mutation_without_file(
    monkeypatch, staff_api_client, room, permission_manage_rooms, media_root
):
    query = """
    mutation createRoomImage($image: Upload!, $room: ID!) {
        roomImageCreate(input: {image: $image, room: $room}) {
            roomErrors {
                code
                field
            }
        }
    }
    """
    variables = {
        "room": graphene.Node.to_global_id("Room", room.id),
        "image": "image name",
    }
    body = get_multipart_request_body(query, variables, file="", file_name="name")
    response = staff_api_client.post_multipart(
        body, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    errors = content["data"]["roomImageCreate"]["roomErrors"]
    assert errors[0]["field"] == "image"
    assert errors[0]["code"] == RoomErrorCode.REQUIRED.name


def test_invalid_room_image_create_mutation(
    staff_api_client, room, permission_manage_rooms
):
    query = """
    mutation createRoomImage($image: Upload!, $room: ID!) {
        roomImageCreate(input: {image: $image, room: $room}) {
            image {
                id
                url
                sortOrder
            }
            errors {
                field
                message
            }
        }
    }
    """
    image_file, image_name = create_pdf_file_with_image_ext()
    variables = {
        "room": graphene.Node.to_global_id("Room", room.id),
        "image": image_name,
    }
    body = get_multipart_request_body(query, variables, image_file, image_name)
    response = staff_api_client.post_multipart(
        body, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    assert content["data"]["roomImageCreate"]["errors"] == [
        {"field": "image", "message": "Invalid file type"}
    ]
    room.refresh_from_db()
    assert room.images.count() == 0


def test_room_image_update_mutation(
    monkeypatch, staff_api_client, room_with_image, permission_manage_rooms
):
    query = """
    mutation updateRoomImage($imageId: ID!, $alt: String) {
        roomImageUpdate(id: $imageId, input: {alt: $alt}) {
            image {
                alt
            }
        }
    }
    """

    mock_create_thumbnails = Mock(return_value=None)
    monkeypatch.setattr(
        (
            "vanphong.graphql.room.mutations.rooms."
            "create_room_thumbnails.delay"
        ),
        mock_create_thumbnails,
    )

    image_obj = room_with_image.images.first()
    alt = "damage alt"
    variables = {
        "alt": alt,
        "imageId": graphene.Node.to_global_id("RoomImage", image_obj.id),
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    assert content["data"]["roomImageUpdate"]["image"]["alt"] == alt

    # We did not update the image field,
    # the image should not have triggered a warm-up
    assert mock_create_thumbnails.call_count == 0


def test_room_image_delete(
    staff_api_client, room_with_image, permission_manage_rooms
):
    room = room_with_image
    query = """
            mutation deleteRoomImage($id: ID!) {
                roomImageDelete(id: $id) {
                    image {
                        id
                        url
                    }
                }
            }
        """
    image_obj = room.images.first()
    node_id = graphene.Node.to_global_id("RoomImage", image_obj.id)
    variables = {"id": node_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomImageDelete"]
    assert image_obj.image.url in data["image"]["url"]
    with pytest.raises(image_obj._meta.model.DoesNotExist):
        image_obj.refresh_from_db()
    assert node_id == data["image"]["id"]


def test_reorder_images(
    staff_api_client, room_with_images, permission_manage_rooms
):
    query = """
    mutation reorderImages($room_id: ID!, $images_ids: [ID]!) {
        roomImageReorder(roomId: $room_id, imagesIds: $images_ids) {
            room {
                id
            }
        }
    }
    """
    room = room_with_images
    images = room.images.all()
    image_0 = images[0]
    image_1 = images[1]
    image_0_id = graphene.Node.to_global_id("RoomImage", image_0.id)
    image_1_id = graphene.Node.to_global_id("RoomImage", image_1.id)
    room_id = graphene.Node.to_global_id("Room", room.id)

    variables = {"room_id": room_id, "images_ids": [image_1_id, image_0_id]}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    get_graphql_content(response)

    # Check if order has been changed
    room.refresh_from_db()
    reordered_images = room.images.all()
    reordered_image_0 = reordered_images[0]
    reordered_image_1 = reordered_images[1]
    assert image_0.id == reordered_image_1.id
    assert image_1.id == reordered_image_0.id


ASSIGN_VARIANT_QUERY = """
    mutation assignVariantImageMutation($variantId: ID!, $imageId: ID!) {
        variantImageAssign(variantId: $variantId, imageId: $imageId) {
            errors {
                field
                message
            }
            roomVariant {
                id
            }
        }
    }
"""


def test_assign_variant_image(
    staff_api_client, user_api_client, room_with_image, permission_manage_rooms
):
    query = ASSIGN_VARIANT_QUERY
    variant = room_with_image.variants.first()
    image = room_with_image.images.first()

    variables = {
        "variantId": to_global_id("RoomVariant", variant.pk),
        "imageId": to_global_id("RoomImage", image.pk),
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    get_graphql_content(response)
    variant.refresh_from_db()
    assert variant.images.first() == image


def test_assign_variant_image_second_time(
    staff_api_client, user_api_client, room_with_image, permission_manage_rooms
):
    # given
    query = ASSIGN_VARIANT_QUERY
    variant = room_with_image.variants.first()
    image = room_with_image.images.first()

    image.variant_images.create(variant=variant)

    variables = {
        "variantId": to_global_id("RoomVariant", variant.pk),
        "imageId": to_global_id("RoomImage", image.pk),
    }

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    # then
    content = get_graphql_content_from_response(response)
    assert "errors" in content
    assert (
        "duplicate key value violates unique constraint"
        in content["errors"][0]["message"]
    )


def test_assign_variant_image_from_different_room(
    staff_api_client, user_api_client, room_with_image, permission_manage_rooms
):
    query = ASSIGN_VARIANT_QUERY
    variant = room_with_image.variants.first()
    room_with_image.pk = None
    room_with_image.slug = "room-with-image"
    room_with_image.save()

    image_2 = RoomImage.objects.create(room=room_with_image)
    variables = {
        "variantId": to_global_id("RoomVariant", variant.pk),
        "imageId": to_global_id("RoomImage", image_2.pk),
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    assert content["data"]["variantImageAssign"]["errors"][0]["field"] == "imageId"

    # check permissions
    response = user_api_client.post_graphql(query, variables)
    assert_no_permission(response)


UNASSIGN_VARIANT_IMAGE_QUERY = """
    mutation unassignVariantImageMutation($variantId: ID!, $imageId: ID!) {
        variantImageUnassign(variantId: $variantId, imageId: $imageId) {
            errors {
                field
                message
            }
            roomVariant {
                id
            }
        }
    }
"""


def test_unassign_variant_image(
    staff_api_client, room_with_image, permission_manage_rooms
):
    query = UNASSIGN_VARIANT_IMAGE_QUERY

    image = room_with_image.images.first()
    variant = room_with_image.variants.first()
    variant.variant_images.create(image=image)

    variables = {
        "variantId": to_global_id("RoomVariant", variant.pk),
        "imageId": to_global_id("RoomImage", image.pk),
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    get_graphql_content(response)
    variant.refresh_from_db()
    assert variant.images.count() == 0


def test_unassign_not_assigned_variant_image(
    staff_api_client, room_with_image, permission_manage_rooms
):
    query = UNASSIGN_VARIANT_IMAGE_QUERY
    variant = room_with_image.variants.first()
    image_2 = RoomImage.objects.create(room=room_with_image)
    variables = {
        "variantId": to_global_id("RoomVariant", variant.pk),
        "imageId": to_global_id("RoomImage", image_2.pk),
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    assert content["data"]["variantImageUnassign"]["errors"][0]["field"] == ("imageId")


@patch("vanphong.room.tasks.update_variants_names.delay")
def test_room_type_update_changes_variant_name(
    mock_update_variants_names,
    staff_api_client,
    room_type,
    room,
    permission_manage_room_types_and_attributes,
):
    query = """
    mutation updateRoomType(
        $id: ID!,
        $hasVariants: Boolean!,
        $isShippingRequired: Boolean!,
        $variantAttributes: [ID],
        ) {
            roomTypeUpdate(
            id: $id,
            input: {
                hasVariants: $hasVariants,
                isShippingRequired: $isShippingRequired,
                variantAttributes: $variantAttributes}) {
                roomType {
                    id
                }
              }
            }
    """
    variant = room.variants.first()
    variant.name = "test name"
    variant.save()
    has_variants = True
    require_shipping = False
    room_type_id = graphene.Node.to_global_id("RoomType", room_type.id)

    variant_attributes = room_type.variant_attributes.all()
    variant_attributes_ids = [
        graphene.Node.to_global_id("Attribute", att.id) for att in variant_attributes
    ]
    variables = {
        "id": room_type_id,
        "hasVariants": has_variants,
        "isShippingRequired": require_shipping,
        "variantAttributes": variant_attributes_ids,
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    get_graphql_content(response)
    variant_attributes = set(variant_attributes)
    variant_attributes_ids = [attr.pk for attr in variant_attributes]
    mock_update_variants_names.assert_called_once_with(
        room_type.pk, variant_attributes_ids
    )


@patch("vanphong.room.tasks._update_variants_names")
def test_room_update_variants_names(mock__update_variants_names, room_type):
    variant_attributes = [room_type.variant_attributes.first()]
    variant_attr_ids = [attr.pk for attr in variant_attributes]
    update_variants_names(room_type.pk, variant_attr_ids)
    assert mock__update_variants_names.call_count == 1


def test_room_variants_by_ids(staff_api_client, variant, channel_USD):
    query = """
        query getRoom($ids: [ID!], $channel: String) {
            roomVariants(ids: $ids, first: 1, channel: $channel) {
                edges {
                    node {
                        id
                        name
                        sku
                        channelListings {
                            channel {
                                id
                                isActive
                                name
                                currencyCode
                            }
                            price {
                                amount
                                currency
                            }
                        }
                    }
                }
            }
        }
    """
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)

    variables = {"ids": [variant_id], "channel": channel_USD.slug}
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["roomVariants"]
    assert data["edges"][0]["node"]["id"] == variant_id
    assert len(data["edges"]) == 1


def test_room_variants_by_customer(user_api_client, variant, channel_USD):
    query = """
        query getRoom($ids: [ID!], $channel: String) {
            roomVariants(ids: $ids, first: 1, channel: $channel) {
                edges {
                    node {
                        id
                        name
                        sku
                        channelListings {
                            channel {
                                id
                                isActive
                                name
                                currencyCode
                            }
                            price {
                                amount
                                currency
                            }
                        }
                    }
                }
            }
        }
    """
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)

    variables = {"ids": [variant_id], "channel": channel_USD.slug}
    response = user_api_client.post_graphql(query, variables)
    assert_no_permission(response)


def test_room_variants_no_ids_list(user_api_client, variant, channel_USD):
    query = """
        query getRoomVariants($channel: String) {
            roomVariants(first: 10, channel: $channel) {
                edges {
                    node {
                        id
                    }
                }
            }
        }
    """
    variables = {"channel": channel_USD.slug}
    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["roomVariants"]
    assert len(data["edges"]) == RoomVariant.objects.count()


@pytest.mark.parametrize(
    "variant_price_amount, api_variant_price",
    [(200, 200), (0, 0)],
)
def test_room_variant_price(
    variant_price_amount,
    api_variant_price,
    user_api_client,
    variant,
    stock,
    channel_USD,
):
    room = variant.room
    RoomVariantChannelListing.objects.filter(
        channel=channel_USD, variant__room_id=room.pk
    ).update(price_amount=variant_price_amount)

    query = """
        query getRoomVariants($id: ID!, $channel: String) {
            room(id: $id, channel: $channel) {
                variants {
                    pricing {
                        priceUndiscounted {
                            gross {
                                amount
                            }
                        }
                    }
                }
            }
        }
        """
    room_id = graphene.Node.to_global_id("Room", variant.room.id)
    variables = {"id": room_id, "channel": channel_USD.slug}
    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["room"]
    variant_price = data["variants"][0]["pricing"]["priceUndiscounted"]["gross"]
    assert variant_price["amount"] == api_variant_price


QUERY_REPORT_ROOM_SALES = """
query TopRooms($period: ReportingPeriod!, $channel: String!) {
    reportRoomSales(period: $period, first: 20, channel: $channel) {
        edges {
            node {
                revenue(period: $period) {
                    gross {
                        amount
                    }
                }
                quantityOrdered
                sku
            }
        }
    }
}
"""


def test_report_room_sales(
    staff_api_client,
    order_with_lines,
    order_with_lines_channel_PLN,
    permission_manage_rooms,
    permission_manage_orders,
    channel_USD,
):
    order = order_with_lines
    variables = {"period": ReportingPeriod.TODAY.name, "channel": channel_USD.slug}
    permissions = [permission_manage_orders, permission_manage_rooms]
    response = staff_api_client.post_graphql(
        QUERY_REPORT_ROOM_SALES, variables, permissions
    )
    content = get_graphql_content(response)
    edges = content["data"]["reportRoomSales"]["edges"]

    node_a = edges[0]["node"]
    line_a = order.lines.get(room_sku=node_a["sku"])
    assert node_a["quantityOrdered"] == line_a.quantity
    amount = str(node_a["revenue"]["gross"]["amount"])
    assert Decimal(amount) == line_a.quantity * line_a.unit_price_gross_amount

    node_b = edges[1]["node"]
    line_b = order.lines.get(room_sku=node_b["sku"])
    assert node_b["quantityOrdered"] == line_b.quantity
    amount = str(node_b["revenue"]["gross"]["amount"])
    assert Decimal(amount) == line_b.quantity * line_b.unit_price_gross_amount


def test_report_room_sales_channel_pln(
    staff_api_client,
    order_with_lines,
    order_with_lines_channel_PLN,
    permission_manage_rooms,
    permission_manage_orders,
    channel_PLN,
):
    order = order_with_lines_channel_PLN
    variables = {"period": ReportingPeriod.TODAY.name, "channel": channel_PLN.slug}
    permissions = [permission_manage_orders, permission_manage_rooms]
    response = staff_api_client.post_graphql(
        QUERY_REPORT_ROOM_SALES, variables, permissions
    )
    content = get_graphql_content(response)
    edges = content["data"]["reportRoomSales"]["edges"]

    node_a = edges[0]["node"]
    line_a = order.lines.get(room_sku=node_a["sku"])
    assert node_a["quantityOrdered"] == line_a.quantity
    amount = str(node_a["revenue"]["gross"]["amount"])
    assert Decimal(amount) == line_a.quantity * line_a.unit_price_gross_amount

    node_b = edges[1]["node"]
    line_b = order.lines.get(room_sku=node_b["sku"])
    assert node_b["quantityOrdered"] == line_b.quantity
    amount = str(node_b["revenue"]["gross"]["amount"])
    assert Decimal(amount) == line_b.quantity * line_b.unit_price_gross_amount


def test_report_room_sales_not_existing_channel(
    staff_api_client,
    order_with_lines,
    order_with_lines_channel_PLN,
    permission_manage_rooms,
    permission_manage_orders,
):
    variables = {"period": ReportingPeriod.TODAY.name, "channel": "not-existing"}
    permissions = [permission_manage_orders, permission_manage_rooms]
    response = staff_api_client.post_graphql(
        QUERY_REPORT_ROOM_SALES, variables, permissions
    )
    content = get_graphql_content(response)
    assert not content["data"]["reportRoomSales"]["edges"]


def test_room_restricted_fields_permissions(
    staff_api_client,
    permission_manage_rooms,
    permission_manage_orders,
    room,
    channel_USD,
):
    """Ensure non-public (restricted) fields are correctly requiring
    the 'manage_rooms' permission.
    """
    query = """
    query Room($id: ID!, $channel: String) {
        room(id: $id, channel: $channel) {
            privateMetadata { __typename}
        }
    }
    """
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }
    permissions = [permission_manage_orders, permission_manage_rooms]
    response = staff_api_client.post_graphql(query, variables, permissions)
    content = get_graphql_content(response)
    assert "privateMetadata" in content["data"]["room"]


@pytest.mark.parametrize(
    "field, is_nested",
    (("digitalContent", True), ("quantityOrdered", False)),
)
def test_variant_restricted_fields_permissions(
    staff_api_client,
    permission_manage_rooms,
    permission_manage_orders,
    room,
    field,
    is_nested,
    channel_USD,
):
    """Ensure non-public (restricted) fields are correctly requiring
    the 'manage_rooms' permission.
    """
    query = """
    query RoomVariant($id: ID!, $channel: String) {
        roomVariant(id: $id, channel: $channel) {
            %(field)s
        }
    }
    """ % {
        "field": field if not is_nested else "%s { __typename }" % field
    }
    variant = room.variants.first()
    variables = {
        "id": graphene.Node.to_global_id("RoomVariant", variant.pk),
        "channel": channel_USD.slug,
    }
    permissions = [permission_manage_orders, permission_manage_rooms]
    response = staff_api_client.post_graphql(query, variables, permissions)
    content = get_graphql_content(response)
    assert field in content["data"]["roomVariant"]


def test_variant_digital_content(
    staff_api_client, permission_manage_rooms, digital_content, channel_USD
):
    query = """
    query Margin($id: ID!, $channel: String) {
        roomVariant(id: $id, channel: $channel) {
            digitalContent{
                id
            }
        }
    }
    """
    variant = digital_content.room_variant
    variables = {
        "id": graphene.Node.to_global_id("RoomVariant", variant.pk),
        "channel": channel_USD.slug,
    }
    permissions = [permission_manage_rooms]
    response = staff_api_client.post_graphql(query, variables, permissions)
    content = get_graphql_content(response)
    assert "digitalContent" in content["data"]["roomVariant"]
    assert "id" in content["data"]["roomVariant"]["digitalContent"]


@pytest.mark.parametrize(
    "collection_filter, count",
    [
        ({"published": "PUBLISHED"}, 2),
        ({"published": "HIDDEN"}, 1),
        ({"search": "-published1"}, 1),
        ({"search": "Collection3"}, 1),
        ({"ids": [to_global_id("Collection", 2), to_global_id("Collection", 3)]}, 2),
    ],
)
def test_collections_query_with_filter(
    collection_filter,
    count,
    query_collections_with_filter,
    channel_USD,
    staff_api_client,
    permission_manage_rooms,
):
    collections = Collection.objects.bulk_create(
        [
            Collection(
                id=1,
                name="Collection1",
                slug="collection-published1",
                description="Test description",
            ),
            Collection(
                id=2,
                name="Collection2",
                slug="collection-published2",
                description="Test description",
            ),
            Collection(
                id=3,
                name="Collection3",
                slug="collection-unpublished",
                description="Test description",
            ),
        ]
    )
    published = (True, True, False)
    CollectionChannelListing.objects.bulk_create(
        [
            CollectionChannelListing(
                channel=channel_USD, collection=collection, is_published=published[num]
            )
            for num, collection in enumerate(collections)
        ]
    )
    collection_filter["channel"] = channel_USD.slug
    variables = {
        "filter": collection_filter,
    }
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query_collections_with_filter, variables)
    content = get_graphql_content(response)
    collections = content["data"]["collections"]["edges"]

    assert len(collections) == count


QUERY_COLLECTIONS_WITH_SORT = """
    query ($sort_by: CollectionSortingInput!) {
        collections(first:5, sortBy: $sort_by) {
                edges{
                    node{
                        name
                    }
                }
            }
        }
"""


@pytest.mark.parametrize(
    "collection_sort, result_order",
    [
        ({"field": "NAME", "direction": "ASC"}, ["Coll1", "Coll2", "Coll3"]),
        ({"field": "NAME", "direction": "DESC"}, ["Coll3", "Coll2", "Coll1"]),
        ({"field": "AVAILABILITY", "direction": "ASC"}, ["Coll2", "Coll1", "Coll3"]),
        ({"field": "AVAILABILITY", "direction": "DESC"}, ["Coll3", "Coll1", "Coll2"]),
        ({"field": "ROOM_COUNT", "direction": "ASC"}, ["Coll1", "Coll3", "Coll2"]),
        ({"field": "ROOM_COUNT", "direction": "DESC"}, ["Coll2", "Coll3", "Coll1"]),
    ],
)
def test_collections_query_with_sort(
    collection_sort,
    result_order,
    staff_api_client,
    permission_manage_rooms,
    room,
    channel_USD,
):
    collections = Collection.objects.bulk_create(
        [
            Collection(name="Coll1", slug="collection-published1"),
            Collection(name="Coll2", slug="collection-unpublished2"),
            Collection(name="Coll3", slug="collection-published"),
        ]
    )
    published = (True, False, True)
    CollectionChannelListing.objects.bulk_create(
        [
            CollectionChannelListing(
                channel=channel_USD, collection=collection, is_published=published[num]
            )
            for num, collection in enumerate(collections)
        ]
    )
    room.collections.add(Collection.objects.get(name="Coll2"))
    collection_sort["channel"] = channel_USD.slug
    variables = {"sort_by": collection_sort}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(QUERY_COLLECTIONS_WITH_SORT, variables)
    content = get_graphql_content(response)
    collections = content["data"]["collections"]["edges"]
    for order, collection_name in enumerate(result_order):
        assert collections[order]["node"]["name"] == collection_name


@pytest.mark.parametrize(
    "category_filter, count",
    [
        ({"search": "slug_"}, 3),
        ({"search": "Category1"}, 1),
        ({"search": "cat1"}, 2),
        ({"search": "Subcategory_description"}, 1),
        ({"ids": [to_global_id("Category", 2), to_global_id("Category", 3)]}, 2),
    ],
)
def test_categories_query_with_filter(
    category_filter,
    count,
    query_categories_with_filter,
    staff_api_client,
    permission_manage_rooms,
):
    Category.objects.create(
        id=1, name="Category1", slug="slug_category1", description="Description cat1"
    )
    Category.objects.create(
        id=2, name="Category2", slug="slug_category2", description="Description cat2"
    )
    Category.objects.create(
        id=3,
        name="SubCategory",
        slug="slug_subcategory",
        parent=Category.objects.get(name="Category1"),
        description="Subcategory_description of cat1",
    )
    variables = {"filter": category_filter}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query_categories_with_filter, variables)
    content = get_graphql_content(response)
    assert content["data"]["categories"]["totalCount"] == count


QUERY_CATEGORIES_WITH_SORT = """
    query ($sort_by: CategorySortingInput!) {
        categories(first:5, sortBy: $sort_by) {
                edges{
                    node{
                        name
                    }
                }
            }
        }
"""


@pytest.mark.parametrize(
    "category_sort, result_order",
    [
        (
            {"field": "NAME", "direction": "ASC"},
            ["Cat1", "Cat2", "SubCat", "SubSubCat"],
        ),
        (
            {"field": "NAME", "direction": "DESC"},
            ["SubSubCat", "SubCat", "Cat2", "Cat1"],
        ),
        (
            {"field": "SUBCATEGORY_COUNT", "direction": "ASC"},
            ["Cat2", "SubSubCat", "Cat1", "SubCat"],
        ),
        (
            {"field": "SUBCATEGORY_COUNT", "direction": "DESC"},
            ["SubCat", "Cat1", "SubSubCat", "Cat2"],
        ),
        (
            {"field": "ROOM_COUNT", "direction": "ASC"},
            ["Cat2", "SubCat", "SubSubCat", "Cat1"],
        ),
        (
            {"field": "ROOM_COUNT", "direction": "DESC"},
            ["Cat1", "SubSubCat", "SubCat", "Cat2"],
        ),
    ],
)
def test_categories_query_with_sort(
    category_sort,
    result_order,
    staff_api_client,
    permission_manage_rooms,
    room_type,
):
    cat1 = Category.objects.create(
        name="Cat1", slug="slug_category1", description="Description cat1"
    )
    Room.objects.create(
        name="Test",
        slug="test",
        room_type=room_type,
        category=cat1,
    )
    Category.objects.create(
        name="Cat2", slug="slug_category2", description="Description cat2"
    )
    Category.objects.create(
        name="SubCat",
        slug="slug_subcategory1",
        parent=Category.objects.get(name="Cat1"),
        description="Subcategory_description of cat1",
    )
    subsubcat = Category.objects.create(
        name="SubSubCat",
        slug="slug_subcategory2",
        parent=Category.objects.get(name="SubCat"),
        description="Subcategory_description of cat1",
    )
    Room.objects.create(
        name="Test2",
        slug="test2",
        room_type=room_type,
        category=subsubcat,
    )
    variables = {"sort_by": category_sort}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(QUERY_CATEGORIES_WITH_SORT, variables)
    content = get_graphql_content(response)
    categories = content["data"]["categories"]["edges"]

    for order, category_name in enumerate(result_order):
        assert categories[order]["node"]["name"] == category_name


@pytest.mark.parametrize(
    "room_type_filter, count",
    [
        ({"configurable": "CONFIGURABLE"}, 2),  # has_variants
        ({"configurable": "SIMPLE"}, 1),  # !has_variants
        ({"roomType": "DIGITAL"}, 1),
        ({"roomType": "SHIPPABLE"}, 2),  # is_shipping_required
    ],
)
def test_room_type_query_with_filter(
    room_type_filter, count, staff_api_client, permission_manage_rooms
):
    query = """
        query ($filter: RoomTypeFilterInput!, ) {
          roomTypes(first:5, filter: $filter) {
            edges{
              node{
                id
                name
              }
            }
          }
        }
        """
    RoomType.objects.bulk_create(
        [
            RoomType(
                name="Digital Type",
                slug="digital-type",
                has_variants=True,
                is_shipping_required=False,
                is_digital=True,
            ),
            RoomType(
                name="Tools",
                slug="tools",
                has_variants=True,
                is_shipping_required=True,
                is_digital=False,
            ),
            RoomType(
                name="Books",
                slug="books",
                has_variants=False,
                is_shipping_required=True,
                is_digital=False,
            ),
        ]
    )

    variables = {"filter": room_type_filter}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    room_types = content["data"]["roomTypes"]["edges"]

    assert len(room_types) == count


QUERY_ROOM_TYPE_WITH_SORT = """
    query ($sort_by: RoomTypeSortingInput!) {
        roomTypes(first:5, sortBy: $sort_by) {
                edges{
                    node{
                        name
                    }
                }
            }
        }
"""


@pytest.mark.parametrize(
    "room_type_sort, result_order",
    [
        ({"field": "NAME", "direction": "ASC"}, ["Digital", "Subscription", "Tools"]),
        ({"field": "NAME", "direction": "DESC"}, ["Tools", "Subscription", "Digital"]),
        # is_digital
        (
            {"field": "DIGITAL", "direction": "ASC"},
            ["Subscription", "Tools", "Digital"],
        ),
        (
            {"field": "DIGITAL", "direction": "DESC"},
            ["Digital", "Tools", "Subscription"],
        ),
        # is_shipping_required
        (
            {"field": "SHIPPING_REQUIRED", "direction": "ASC"},
            ["Digital", "Subscription", "Tools"],
        ),
        (
            {"field": "SHIPPING_REQUIRED", "direction": "DESC"},
            ["Tools", "Subscription", "Digital"],
        ),
    ],
)
def test_room_type_query_with_sort(
    room_type_sort, result_order, staff_api_client, permission_manage_rooms
):
    RoomType.objects.bulk_create(
        [
            RoomType(
                name="Digital",
                slug="digital",
                has_variants=True,
                is_shipping_required=False,
                is_digital=True,
            ),
            RoomType(
                name="Tools",
                slug="tools",
                has_variants=True,
                is_shipping_required=True,
                is_digital=False,
            ),
            RoomType(
                name="Subscription",
                slug="subscription",
                has_variants=False,
                is_shipping_required=False,
                is_digital=False,
            ),
        ]
    )

    variables = {"sort_by": room_type_sort}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(QUERY_ROOM_TYPE_WITH_SORT, variables)
    content = get_graphql_content(response)
    room_types = content["data"]["roomTypes"]["edges"]

    for order, room_type_name in enumerate(result_order):
        assert room_types[order]["node"]["name"] == room_type_name


NOT_EXISTS_IDS_COLLECTIONS_QUERY = """
    query ($filter: RoomTypeFilterInput!) {
        roomTypes(first: 5, filter: $filter) {
            edges {
                node {
                    id
                    name
                }
            }
        }
    }
"""


def test_room_types_query_ids_not_exists(user_api_client, category):
    query = NOT_EXISTS_IDS_COLLECTIONS_QUERY
    variables = {"filter": {"ids": ["fTEJRuFHU6fd2RU=", "2XwnQNNhwCdEjhP="]}}
    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response, ignore_errors=True)
    message_error = '{"ids": [{"message": "Invalid ID specified.", "code": ""}]}'

    assert len(content["errors"]) == 1
    assert content["errors"][0]["message"] == message_error
    assert content["data"]["roomTypes"] is None


QUERY_AVAILABLE_ATTRIBUTES = """
    query($roomTypeId:ID!, $filters: AttributeFilterInput) {
      roomType(id: $roomTypeId) {
        availableAttributes(first: 10, filter: $filters) {
          edges {
            node {
              id
              slug
            }
          }
        }
      }
    }
"""


def test_room_type_get_unassigned_room_type_attributes(
    staff_api_client, permission_manage_rooms
):
    query = QUERY_AVAILABLE_ATTRIBUTES
    target_room_type, ignored_room_type = RoomType.objects.bulk_create(
        [
            RoomType(name="Type 1", slug="type-1"),
            RoomType(name="Type 2", slug="type-2"),
        ]
    )

    unassigned_attributes = list(
        Attribute.objects.bulk_create(
            [
                Attribute(slug="size", name="Size", type=AttributeType.ROOM_TYPE),
                Attribute(
                    slug="weight", name="Weight", type=AttributeType.ROOM_TYPE
                ),
                Attribute(
                    slug="thickness", name="Thickness", type=AttributeType.ROOM_TYPE
                ),
            ]
        )
    )

    unassigned_page_attributes = list(
        Attribute.objects.bulk_create(
            [
                Attribute(slug="length", name="Length", type=AttributeType.PAGE_TYPE),
                Attribute(slug="width", name="Width", type=AttributeType.PAGE_TYPE),
            ]
        )
    )

    assigned_attributes = list(
        Attribute.objects.bulk_create(
            [
                Attribute(slug="color", name="Color", type=AttributeType.ROOM_TYPE),
                Attribute(slug="type", name="Type", type=AttributeType.ROOM_TYPE),
            ]
        )
    )

    # Ensure that assigning them to another room type
    # doesn't return an invalid response
    ignored_room_type.room_attributes.add(*unassigned_attributes)
    ignored_room_type.room_attributes.add(*unassigned_page_attributes)

    # Assign the other attributes to the target room type
    target_room_type.room_attributes.add(*assigned_attributes)

    gql_unassigned_attributes = get_graphql_content(
        staff_api_client.post_graphql(
            query,
            {
                "roomTypeId": graphene.Node.to_global_id(
                    "RoomType", target_room_type.pk
                )
            },
            permissions=[permission_manage_rooms],
        )
    )["data"]["roomType"]["availableAttributes"]["edges"]

    assert len(gql_unassigned_attributes) == len(
        unassigned_attributes
    ), gql_unassigned_attributes

    received_ids = sorted((attr["node"]["id"] for attr in gql_unassigned_attributes))
    expected_ids = sorted(
        (
            graphene.Node.to_global_id("Attribute", attr.pk)
            for attr in unassigned_attributes
        )
    )

    assert received_ids == expected_ids


def test_room_type_filter_unassigned_attributes(
    staff_api_client, permission_manage_rooms, room_type_attribute_list
):
    expected_attribute = room_type_attribute_list[0]
    query = QUERY_AVAILABLE_ATTRIBUTES
    room_type = RoomType.objects.create(name="Empty Type")
    room_type_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    filters = {"search": expected_attribute.name}

    found_attributes = get_graphql_content(
        staff_api_client.post_graphql(
            query,
            {"roomTypeId": room_type_id, "filters": filters},
            permissions=[permission_manage_rooms],
        )
    )["data"]["roomType"]["availableAttributes"]["edges"]

    assert len(found_attributes) == 1

    _, attribute_id = graphene.Node.from_global_id(found_attributes[0]["node"]["id"])
    assert attribute_id == str(expected_attribute.pk)


QUERY_FILTER_ROOM_TYPES = """
    query($filters: RoomTypeFilterInput) {
      roomTypes(first: 10, filter: $filters) {
        edges {
          node {
            name
          }
        }
      }
    }
"""


@pytest.mark.parametrize(
    "search, expected_names",
    (
        ("", ["The best juices", "The best beers", "The worst beers"]),
        ("best", ["The best juices", "The best beers"]),
        ("worst", ["The worst beers"]),
        ("average", []),
    ),
)
def test_filter_room_types_by_custom_search_value(
    api_client, search, expected_names
):
    query = QUERY_FILTER_ROOM_TYPES

    RoomType.objects.bulk_create(
        [
            RoomType(name="The best juices", slug="best-juices"),
            RoomType(name="The best beers", slug="best-beers"),
            RoomType(name="The worst beers", slug="worst-beers"),
        ]
    )

    variables = {"filters": {"search": search}}

    results = get_graphql_content(api_client.post_graphql(query, variables))["data"][
        "roomTypes"
    ]["edges"]

    assert len(results) == len(expected_names)
    matched_names = sorted([result["node"]["name"] for result in results])

    assert matched_names == sorted(expected_names)


def test_room_filter_by_attribute_values(
    user_api_client,
    permission_manage_rooms,
    color_attribute,
    pink_attribute_value,
    room_with_variant_with_two_attributes,
    channel_USD,
):
    query = """
    query Rooms($filters: RoomFilterInput, $channel: String) {
      rooms(first: 5, filter: $filters, channel: $channel) {
        edges {
        node {
          id
          name
          attributes {
            attribute {
              name
              slug
            }
            values {
              name
              slug
            }
          }
        }
        }
      }
    }
    """
    variables = {
        "attributes": [
            {"slug": color_attribute.slug, "values": [pink_attribute_value.slug]}
        ],
        "channel": channel_USD.slug,
    }
    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    assert not content["data"]["rooms"]["edges"] == [
        {
            "node": {
                "attributes": [],
                "name": room_with_variant_with_two_attributes.name,
            }
        }
    ]


MUTATION_CREATE_ROOM_WITH_STOCKS = """
mutation createRoom(
        $roomType: ID!,
        $category: ID!
        $name: String!,
        $sku: String,
        $stocks: [StockInput!],
        $basePrice: PositiveDecimal!,
        $trackInventory: Boolean,
        $country: CountryCode
        )
    {
        roomCreate(
            input: {
                category: $category,
                roomType: $roomType,
                name: $name,
                sku: $sku,
                stocks: $stocks,
                trackInventory: $trackInventory,
                basePrice: $basePrice,
            })
        {
            room {
                id
                name
                variants{
                    id
                    sku
                    trackInventory
                    quantityAvailable(countryCode: $country)
                }
            }
            roomErrors {
                message
                field
                code
            }
        }
    }
    """


def test_create_stocks_failed(room_with_single_variant, hotel):
    variant = room_with_single_variant.variants.first()

    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    stocks_data = [
        {"quantity": 10, "hotel": "123"},
        {"quantity": 10, "hotel": "321"},
    ]
    hotels = [hotel, second_hotel]
    with pytest.raises(ValidationError):
        create_stocks(variant, stocks_data, hotels)


def test_create_stocks(variant, hotel):
    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    assert variant.stocks.count() == 0

    stocks_data = [
        {"quantity": 10, "hotel": "123"},
        {"quantity": 10, "hotel": "321"},
    ]
    hotels = [hotel, second_hotel]
    create_stocks(variant, stocks_data, hotels)

    assert variant.stocks.count() == len(stocks_data)
    assert {stock.hotel.pk for stock in variant.stocks.all()} == {
        hotel.pk for hotel in hotels
    }
    assert {stock.quantity for stock in variant.stocks.all()} == {
        data["quantity"] for data in stocks_data
    }


def test_update_or_create_variant_stocks(variant, hotels):
    Stock.objects.create(
        room_variant=variant,
        hotel=hotels[0],
        quantity=5,
    )
    stocks_data = [
        {"quantity": 10, "hotel": "123"},
        {"quantity": 10, "hotel": "321"},
    ]

    RoomVariantStocksUpdate.update_or_create_variant_stocks(
        variant, stocks_data, hotels
    )

    variant.refresh_from_db()
    assert variant.stocks.count() == 2
    assert {stock.hotel.pk for stock in variant.stocks.all()} == {
        hotel.pk for hotel in hotels
    }
    assert {stock.quantity for stock in variant.stocks.all()} == {
        data["quantity"] for data in stocks_data
    }


def test_update_or_create_variant_stocks_empty_stocks_data(variant, hotels):
    Stock.objects.create(
        room_variant=variant,
        hotel=hotels[0],
        quantity=5,
    )

    RoomVariantStocksUpdate.update_or_create_variant_stocks(variant, [], hotels)

    variant.refresh_from_db()
    assert variant.stocks.count() == 1
    stock = variant.stocks.first()
    assert stock.hotel == hotels[0]
    assert stock.quantity == 5


# Because we use Scalars for Weight this test query tests only a scenario when weight
# value is passed by a variable
MUTATION_CREATE_ROOM_WITH_WEIGHT_GQL_VARIABLE = """
mutation createRoom(
        $roomType: ID!,
        $category: ID!
        $name: String!,
        $weight: WeightScalar)
    {
        roomCreate(
            input: {
                category: $category,
                roomType: $roomType,
                name: $name,
                weight: $weight
            })
        {
            room {
                id
                weight{
                    value
                    unit
                }
            }
            roomErrors {
                message
                field
                code
            }
        }
    }
    """


@pytest.mark.parametrize(
    "weight, expected_weight_value",
    (
        ("0", 0),
        (0, 0),
        (11.11, 11.11),
        (11, 11.0),
        ("11.11", 11.11),
        ({"value": 11.11, "unit": "kg"}, 11.11),
        ({"value": 11, "unit": "g"}, 0.011),
        ({"value": "1", "unit": "ounce"}, 0.028),
    ),
)
def test_create_room_with_weight_variable(
    weight,
    expected_weight_value,
    staff_api_client,
    category,
    permission_manage_rooms,
    room_type_without_variant,
    site_settings,
):
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_type_id = graphene.Node.to_global_id(
        "RoomType", room_type_without_variant.pk
    )
    variables = {
        "category": category_id,
        "roomType": room_type_id,
        "name": "Test",
        "weight": weight,
    }
    response = staff_api_client.post_graphql(
        MUTATION_CREATE_ROOM_WITH_WEIGHT_GQL_VARIABLE,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    result_weight = content["data"]["roomCreate"]["room"]["weight"]
    assert result_weight["value"] == expected_weight_value
    assert result_weight["unit"] == site_settings.default_weight_unit.upper()


@pytest.mark.parametrize(
    "weight, expected_weight_value",
    (
        ("0", 0),
        (0, 0),
        ("11.11", 11.11),
        ("11", 11.0),
        ('"11.11"', 11.11),
        ('{value: 11.11, unit: "kg"}', 11.11),
        ('{value: 11, unit: "g"}', 0.011),
        ('{value: "1", unit: "ounce"}', 0.028),
    ),
)
def test_create_room_with_weight_input(
    weight,
    expected_weight_value,
    staff_api_client,
    category,
    permission_manage_rooms,
    room_type_without_variant,
    site_settings,
):
    # Because we use Scalars for Weight this test query tests only a scenario when
    # weight value is passed by directly in input
    query = f"""
    mutation createRoom(
            $roomType: ID!,
            $category: ID!,
            $name: String!)
        {{
            roomCreate(
                input: {{
                    category: $category,
                    roomType: $roomType,
                    name: $name,
                    weight: {weight}
                }})
            {{
                room {{
                    id
                    weight{{
                        value
                        unit
                    }}
                }}
                roomErrors {{
                    message
                    field
                    code
                }}
            }}
        }}
    """
    category_id = graphene.Node.to_global_id("Category", category.pk)
    room_type_id = graphene.Node.to_global_id(
        "RoomType", room_type_without_variant.pk
    )
    variables = {
        "category": category_id,
        "roomType": room_type_id,
        "name": "Test",
    }
    response = staff_api_client.post_graphql(
        query,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    result_weight = content["data"]["roomCreate"]["room"]["weight"]
    assert result_weight["value"] == expected_weight_value
    assert result_weight["unit"] == site_settings.default_weight_unit.upper()
