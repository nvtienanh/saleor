import graphene

from ....core.permissions import RoomPermissions
from ....hotel.models import Stock
from ....hotel.tests.utils import get_quantity_allocated_for_stock
from ...tests.utils import assert_no_permission, get_graphql_content

QUERY_STOCK = """
query stock($id: ID!) {
    stock(id: $id) {
        hotel {
            name
        }
        roomVariant {
            room {
                name
            }
        }
        quantity
        quantityAllocated
    }
}
"""


QUERY_STOCKS = """
    query {
        stocks(first:100) {
            totalCount
            edges {
                node {
                    id
                    hotel {
                        name
                        id
                    }
                    roomVariant {
                        name
                        id
                    }
                    quantity
                    quantityAllocated
                }
            }
        }
    }
"""

QUERY_STOCKS_WITH_FILTERS = """
    query stocks($filter: StockFilterInput!) {
        stocks(first: 100, filter: $filter) {
            totalCount
            edges {
                node {
                    id
                }
            }
        }
    }
"""


def test_query_stock_requires_permission(staff_api_client, stock):
    assert not staff_api_client.user.has_perm(RoomPermissions.MANAGE_ROOMS)
    stock_id = graphene.Node.to_global_id("Stock", stock.pk)
    response = staff_api_client.post_graphql(QUERY_STOCK, variables={"id": stock_id})
    assert_no_permission(response)


def test_query_stock(staff_api_client, stock, permission_manage_rooms):
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    stock_id = graphene.Node.to_global_id("Stock", stock.pk)
    response = staff_api_client.post_graphql(QUERY_STOCK, variables={"id": stock_id})
    content = get_graphql_content(response)
    content_stock = content["data"]["stock"]
    assert (
        content_stock["roomVariant"]["room"]["name"]
        == stock.room_variant.room.name
    )
    assert content_stock["hotel"]["name"] == stock.hotel.name
    assert content_stock["quantity"] == stock.quantity
    assert content_stock["quantityAllocated"] == get_quantity_allocated_for_stock(stock)


def test_query_stocks_requires_permissions(staff_api_client):
    assert not staff_api_client.user.has_perm(RoomPermissions.MANAGE_ROOMS)
    response = staff_api_client.post_graphql(QUERY_STOCKS)
    assert_no_permission(response)


def test_query_stocks(staff_api_client, stock, permission_manage_rooms):
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    response = staff_api_client.post_graphql(QUERY_STOCKS)
    content = get_graphql_content(response)
    total_count = content["data"]["stocks"]["totalCount"]
    assert total_count == Stock.objects.count()


def test_query_stocks_with_filters_quantity(
    staff_api_client, stock, permission_manage_rooms
):
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    quantities = Stock.objects.all().values_list("quantity", flat=True)
    sum_quantities = sum(quantities)
    variables = {"filter": {"quantity": sum_quantities}}
    response = staff_api_client.post_graphql(
        QUERY_STOCKS_WITH_FILTERS, variables=variables
    )
    content = get_graphql_content(response)
    total_count = content["data"]["stocks"]["totalCount"]
    assert total_count == 0

    variables = {"filter": {"quantity": max(quantities)}}
    response = staff_api_client.post_graphql(
        QUERY_STOCKS_WITH_FILTERS, variables=variables
    )
    content = get_graphql_content(response)
    total_count = content["data"]["stocks"]["totalCount"]
    assert total_count == Stock.objects.filter(quantity=max(quantities)).count()


def test_query_stocks_with_filters_hotel(
    staff_api_client, stock, permission_manage_rooms
):
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    hotel = stock.hotel
    response_name = staff_api_client.post_graphql(
        QUERY_STOCKS_WITH_FILTERS, variables={"filter": {"search": hotel.name}}
    )
    content = get_graphql_content(response_name)
    total_count = content["data"]["stocks"]["totalCount"]
    assert total_count == Stock.objects.filter(hotel=hotel).count()


def test_query_stocks_with_filters_room_variant(
    staff_api_client, stock, permission_manage_rooms
):
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    room_variant = stock.room_variant
    response_name = staff_api_client.post_graphql(
        QUERY_STOCKS_WITH_FILTERS,
        variables={"filter": {"search": room_variant.name}},
    )
    content = get_graphql_content(response_name)
    total_count = content["data"]["stocks"]["totalCount"]
    assert (
        total_count
        == Stock.objects.filter(room_variant__name=room_variant.name).count()
    )


def test_query_stocks_with_filters_room_variant__room(
    staff_api_client, stock, permission_manage_rooms
):
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    room = stock.room_variant.room
    response_name = staff_api_client.post_graphql(
        QUERY_STOCKS_WITH_FILTERS, variables={"filter": {"search": room.name}}
    )
    content = get_graphql_content(response_name)
    total_count = content["data"]["stocks"]["totalCount"]
    assert (
        total_count
        == Stock.objects.filter(room_variant__room__name=room.name).count()
    )
