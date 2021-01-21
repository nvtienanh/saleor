import graphene
import pytest

from ....tests.utils import get_graphql_content


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_category_view(api_client, category_with_rooms, count_queries, channel_USD):
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

        fragment Price on TaxedMoney {
          gross {
            amount
            currency
          }
          net {
            amount
            currency
          }
        }

        fragment RoomPricingField on Room {
          pricing {
            onSale
            priceRangeUndiscounted {
              start {
                ...Price
              }
              stop {
                ...Price
              }
            }
            priceRange {
              start {
                ...Price
              }
              stop {
                ...Price
              }
            }
          }
        }

        query Category($id: ID!, $pageSize: Int, $channel: String) {
          rooms (
            first: $pageSize,
            filter: {categories: [$id]},
            channel: $channel
          ) {
            totalCount
            edges {
              node {
                ...BasicRoomFields
                ...RoomPricingField
                category {
                  id
                  name
                }
              }
            }
            pageInfo {
              endCursor
              hasNextPage
              hasPreviousPage
              startCursor
            }
          }
          category(id: $id) {
            seoDescription
            seoTitle
            id
            name
            backgroundImage {
              url
            }
            ancestors(last: 5) {
              edges {
                node {
                  id
                  name
                }
              }
            }
          }
          attributes(filter: {inCategory: $id, channel: $channel}, first: 100) {
            edges {
              node {
                id
                name
                slug
                values {
                  id
                  name
                  slug
                }
              }
            }
          }
        }
    """
    variables = {
        "pageSize": 100,
        "id": graphene.Node.to_global_id("Category", category_with_rooms.pk),
        "channel": channel_USD.slug,
    }
    get_graphql_content(api_client.post_graphql(query, variables))
