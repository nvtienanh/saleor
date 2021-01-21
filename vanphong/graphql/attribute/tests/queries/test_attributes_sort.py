from typing import TYPE_CHECKING, Union

import graphene
import pytest

from .....attribute import AttributeType
from .....attribute.models import Attribute
from .....attribute.utils import associate_attribute_values_to_instance
from ....tests.utils import get_graphql_content

if TYPE_CHECKING:
    from .....room.models import Room, RoomVariant


ATTRIBUTES_SORT_QUERY = """
    query($sortBy: AttributeSortingInput) {
      attributes(first: 10, sortBy: $sortBy) {
        edges {
          node {
            slug
          }
        }
      }
    }
"""


def test_sort_attributes_by_slug(api_client):
    Attribute.objects.bulk_create(
        [
            Attribute(name="MyAttribute", slug="b", type=AttributeType.ROOM_TYPE),
            Attribute(name="MyAttribute", slug="a", type=AttributeType.ROOM_TYPE),
        ]
    )

    variables = {"sortBy": {"field": "SLUG", "direction": "ASC"}}

    attributes = get_graphql_content(
        api_client.post_graphql(ATTRIBUTES_SORT_QUERY, variables)
    )["data"]["attributes"]["edges"]

    assert len(attributes) == 2
    assert attributes[0]["node"]["slug"] == "a"
    assert attributes[1]["node"]["slug"] == "b"


def test_sort_attributes_by_default_sorting(api_client):
    """Don't provide any sorting, this should sort by slug by default."""
    Attribute.objects.bulk_create(
        [
            Attribute(name="A", slug="b", type=AttributeType.ROOM_TYPE),
            Attribute(name="B", slug="a", type=AttributeType.ROOM_TYPE),
        ]
    )

    attributes = get_graphql_content(
        api_client.post_graphql(ATTRIBUTES_SORT_QUERY, {})
    )["data"]["attributes"]["edges"]

    assert len(attributes) == 2
    assert attributes[0]["node"]["slug"] == "a"
    assert attributes[1]["node"]["slug"] == "b"


@pytest.mark.parametrize("is_variant", (True, False))
def test_attributes_of_rooms_are_sorted(
    user_api_client, room, color_attribute, is_variant, channel_USD
):
    """Ensures the attributes of rooms and variants are sorted."""

    variant = room.variants.first()

    if is_variant:
        query = """
            query($id: ID!, $channel: String) {
              roomVariant(id: $id, channel: $channel) {
                attributes {
                  attribute {
                    id
                  }
                }
              }
            }
        """
    else:
        query = """
            query($id: ID!, $channel: String) {
              room(id: $id, channel: $channel) {
                attributes {
                  attribute {
                    id
                  }
                }
              }
            }
        """

    # Create a dummy attribute with a higher ID
    # This will allow us to make sure it is always the last attribute
    # when sorted by ID. Thus, we are sure the query is actually passing the test.
    other_attribute = Attribute.objects.create(name="Other", slug="other")

    # Add the attribute to the room type
    if is_variant:
        room.room_type.variant_attributes.set([color_attribute, other_attribute])
    else:
        room.room_type.room_attributes.set([color_attribute, other_attribute])

    # Retrieve the M2M object for the attribute vs the room type
    if is_variant:
        m2m_rel_other_attr = other_attribute.attributevariant.last()
    else:
        m2m_rel_other_attr = other_attribute.attributeroom.last()

    # Push the last attribute to the top and let the others to None
    m2m_rel_other_attr.sort_order = 0
    m2m_rel_other_attr.save(update_fields=["sort_order"])

    # Assign attributes to the room
    node = variant if is_variant else room  # type: Union[Room, RoomVariant]
    node.attributesrelated.clear()
    associate_attribute_values_to_instance(
        node, color_attribute, color_attribute.values.first()
    )

    # Sort the database attributes by their sort order and ID (when None)
    expected_order = [other_attribute.pk, color_attribute.pk]

    # Make the node ID
    if is_variant:
        node_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    else:
        node_id = graphene.Node.to_global_id("Room", room.pk)

    # Retrieve the attributes
    data = get_graphql_content(
        user_api_client.post_graphql(
            query, {"id": node_id, "channel": channel_USD.slug}
        )
    )["data"]
    attributes = data["roomVariant" if is_variant else "room"]["attributes"]
    actual_order = [
        int(graphene.Node.from_global_id(attr["attribute"]["id"])[1])
        for attr in attributes
    ]

    # Compare the received data against our expectations
    assert actual_order == expected_order
