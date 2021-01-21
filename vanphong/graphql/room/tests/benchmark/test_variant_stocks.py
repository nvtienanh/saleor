import graphene
import pytest

from .....hotel.models import Stock, Hotel
from ....tests.utils import get_graphql_content


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_room_variants_stocks_create(
    staff_api_client, variant, hotel, permission_manage_rooms, count_queries
):
    query = """
    mutation RoomVariantStocksCreate($variantId: ID!, $stocks: [StockInput!]!){
        roomVariantStocksCreate(variantId: $variantId, stocks: $stocks){
            roomVariant{
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
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    stocks_count = variant.stocks.count()

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
        query,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksCreate"]
    assert not data["bulkStockErrors"]
    assert (
        len(data["roomVariant"]["stocks"])
        == variant.stocks.count()
        == stocks_count + len(stocks)
    )


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_room_variants_stocks_update(
    staff_api_client, variant, hotel, permission_manage_rooms, count_queries
):
    query = """
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
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.slug = "second hotel"
    second_hotel.pk = None
    second_hotel.save()

    Stock.objects.create(room_variant=variant, hotel=hotel, quantity=10)

    stocks_count = variant.stocks.count()

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
        query,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksUpdate"]

    assert not data["bulkStockErrors"]
    assert len(data["roomVariant"]["stocks"]) == len(stocks)
    assert variant.stocks.count() == stocks_count + 1


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_room_variants_stocks_delete(
    staff_api_client, variant, hotel, permission_manage_rooms, count_queries
):
    query = """
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
        query,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantStocksDelete"]

    assert not data["stockErrors"]
    assert (
        len(data["roomVariant"]["stocks"])
        == variant.stocks.count()
        == stocks_count - 1
    )
