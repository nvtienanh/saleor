import pytest
from graphene import Node

from ....tests.utils import get_graphql_content


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_room_details(room_with_image, api_client, count_queries, channel_USD):
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
          images {
            id
            url
          }
        }

        query RoomDetails($id: ID!, $channel: String) {
          room(id: $id, channel: $channel) {
            ...BasicRoomFields
            description
            category {
              id
              name
              rooms(first: 4, channel: $channel) {
                edges {
                  node {
                    ...BasicRoomFields
                    category {
                      id
                      name
                    }
                    pricing {
                      priceRange {
                        start{
                          currency
                          gross {
                            amount
                            localized
                          }
                        }
                        stop{
                          currency
                          gross {
                            amount
                            localized
                          }
                        }
                      }
                      priceRangeUndiscounted {
                        start{
                          currency
                          gross {
                            amount
                            localized
                          }
                        }
                        stop{
                          currency
                          gross {
                            amount
                            localized
                          }
                        }
                      }
                      priceRangeLocalCurrency {
                        start{
                          currency
                          gross {
                            amount
                            localized
                          }
                        }
                        stop{
                          currency
                          gross {
                            amount
                            localized
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            images {
              id
              url
            }
            variants {
              ...RoomVariantFields
            }
            seoDescription
            seoTitle
            isAvailable
          }
        }
    """
    room = room_with_image
    variant = room_with_image.variants.first()
    image = room_with_image.get_first_image()
    image.variant_images.create(variant=variant)

    variables = {
        "id": Node.to_global_id("Room", room.pk),
        "channel": channel_USD.slug,
    }
    get_graphql_content(api_client.post_graphql(query, variables))


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_retrieve_room_attributes(
    room_list, api_client, count_queries, channel_USD
):
    query = """
        query($sortBy: RoomOrder, $channel: String) {
          rooms(first: 10, sortBy: $sortBy, channel: $channel) {
            edges {
              node {
                id
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

    variables = {"channel": channel_USD.slug}
    get_graphql_content(api_client.post_graphql(query, variables))


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_retrieve_channel_listings(
    room_list_with_many_channels,
    staff_api_client,
    count_queries,
    permission_manage_rooms,
    channel_USD,
):
    query = """
        query($channel: String) {
          rooms(first: 10, channel: $channel) {
            edges {
              node {
                id
                channelListings {
                  publicationDate
                  isPublished
                  channel{
                    slug
                    currencyCode
                    name
                    isActive
                  }
                  visibleInListings
                  discountedPrice{
                    amount
                    currency
                  }
                  purchaseCost{
                    start{
                      amount
                    }
                    stop{
                      amount
                    }
                  }
                  margin{
                    start
                    stop
                  }
                  isAvailableForPurchase
                  availableForPurchase
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
          }
        }
    """

    variables = {"channel": channel_USD.slug}
    get_graphql_content(
        staff_api_client.post_graphql(
            query,
            variables,
            permissions=(permission_manage_rooms,),
            check_no_permissions=False,
        )
    )


@pytest.mark.django_db
@pytest.mark.count_queries(autouse=False)
def test_retrive_rooms_with_room_types_and_attributes(
    room_list,
    api_client,
    count_queries,
    channel_USD,
):
    query = """
        query($channel: String) {
          rooms(first: 10, channel: $channel) {
            edges {
              node {
                id
                  roomType {
                    name
                  roomAttributes {
                    name
                  }
                  variantAttributes {
                    name
                  }
                }
              }
            }
          }
        }
    """
    variables = {"channel": channel_USD.slug}
    get_graphql_content(api_client.post_graphql(query, variables))
