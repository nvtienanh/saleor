from uuid import uuid4

import graphene
import pytest

from .....room.models import RoomVariant
from .....hotel.models import Stock
from ....tests.utils import get_graphql_content


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_retrieve_variant_list(
    room_variant_list,
    api_client,
    count_queries,
    hotel,
    hotel_no_shipping_zone,
    shipping_zone_without_countries,
    channel_USD,
):
    query = """
        fragment BasicRoomFields on Room {
          id
          name
          thumbnail {
            url
            alt
          }
          thumbnail2x: thumbnail(size: 510) {
            url
          }
        }

        fragment RoomVariantFields on RoomVariant {
          id
          sku
          name
          pricing {
            discountLocalCurrency {
              currency
              gross {
                amount
                localized
              }
            }
            price {
              currency
              gross {
                amount
                localized
              }
            }
            priceUndiscounted {
              currency
              gross {
                amount
                localized
              }
            }
            priceLocalCurrency {
              currency
              gross {
                amount
                localized
              }
            }
          }
          attributes {
            attribute {
              id
              name
            }
            values {
              id
              name
              value: name
            }
          }
        }

        query VariantList($ids: [ID!], $channel: String) {
          roomVariants(ids: $ids, first: 100, channel: $channel) {
            edges {
              node {
                ...RoomVariantFields
                quantityAvailable
                quantityAvailablePl: quantityAvailable(countryCode: PL)
                quantityAvailableUS: quantityAvailable(countryCode: US)
                room {
                  ...BasicRoomFields
                }
              }
            }
          }
        }
    """
    hotel_2 = hotel_no_shipping_zone
    hotel_2.shipping_zones.add(shipping_zone_without_countries)
    stocks = [
        Stock(room_variant=variant, hotel=hotel, quantity=1)
        for variant in room_variant_list
    ]
    stocks.extend(
        [
            Stock(room_variant=variant, hotel=hotel_2, quantity=2)
            for variant in room_variant_list
        ]
    )
    Stock.objects.bulk_create(stocks)

    variables = {
        "ids": [
            graphene.Node.to_global_id("RoomVariant", variant.pk)
            for variant in room_variant_list
        ],
        "channel": channel_USD.slug,
    }
    get_graphql_content(api_client.post_graphql(query, variables))


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_room_variant_bulk_create(
    staff_api_client,
    room_with_variant_with_two_attributes,
    permission_manage_rooms,
    color_attribute,
    size_attribute,
    count_queries,
):
    query = """
    mutation RoomVariantBulkCreate(
        $variants: [RoomVariantBulkCreateInput]!, $roomId: ID!
    ) {
        roomVariantBulkCreate(variants: $variants, room: $roomId) {
            bulkRoomErrors {
                field
                message
                code
                index
            }
            roomVariants{
                id
                sku
            }
            count
        }
    }
    """
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
    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["roomVariantBulkCreate"]
    assert not data["bulkRoomErrors"]
    assert data["count"] == 1
    assert room_variant_count + 1 == RoomVariant.objects.count()
