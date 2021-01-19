import graphene

from ...tests.utils import get_graphql_content

QUERY_PRICING_ON_ROOM_CHANNEL_LISTING = """
query FetchRoom($id: ID, $channel: String) {
  room(id: $id, channel: $channel) {
    id
    pricing {
      priceRangeUndiscounted {
        start {
          gross {
            amount
            currency
          }
        }
        stop {
          gross {
            amount
            currency
          }
        }
      }
    }
    channelListings {
      channel {
        slug
      }
      pricing {
        priceRangeUndiscounted {
          start {
            gross {
              amount
              currency
            }
          }
          stop {
            gross {
              amount
              currency
            }
          }
        }
      }
    }
  }
}
"""


def test_room_channel_listing_pricing_field(
    staff_api_client, permission_manage_rooms, channel_USD, room
):
    # given
    variables = {
        "id": graphene.Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }
    room.channel_listings.exclude(channel__slug=channel_USD.slug).delete()

    # when
    response = staff_api_client.post_graphql(
        QUERY_PRICING_ON_ROOM_CHANNEL_LISTING,
        variables=variables,
        permissions=(permission_manage_rooms,),
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    room_data = content["data"]["room"]
    room_channel_listing_data = room_data["channelListings"][0]
    assert room_data["pricing"] == room_channel_listing_data["pricing"]
