import os.path
from decimal import Decimal

import graphene
import pytest

from ....attribute import AttributeType
from ....attribute import models as attribute_models
from ....attribute.utils import associate_attribute_values_to_instance
from ....room import models as room_models
from ...tests.utils import get_graphql_content

HERE = os.path.realpath(os.path.dirname(__file__))

QUERY_SORT_ROOMS_BY_ATTRIBUTE = """
query rooms(
  $field: RoomOrderField
  $attributeId: ID
  $direction: OrderDirection!
  $channel: String
) {
  rooms(
    first: 100,
    channel: $channel,
    sortBy: { field: $field, attributeId: $attributeId, direction: $direction }
  ) {
    edges {
      node {
        name
        attributes {
          attribute {
            slug
          }
          values {
            name
          }
        }
      }
    }
  }
}
"""

COLORS = (["Blue", "Red"], ["Blue", "Gray"], ["Pink"], ["Pink"], ["Green"])
TRADEMARKS = ("A", "A", "ab", "b", "y")
DUMMIES = ("Oopsie",)


@pytest.fixture
def rooms_structures(category, channel_USD):
    def attr_value(attribute, *values):
        return [attribute.values.get_or_create(name=v, slug=v)[0] for v in values]

    assert room_models.Room.objects.count() == 0

    in_multivals = attribute_models.AttributeInputType.MULTISELECT

    pt_apples, pt_oranges, pt_other = list(
        room_models.RoomType.objects.bulk_create(
            [
                room_models.RoomType(
                    name="Apples", slug="apples", has_variants=False
                ),
                room_models.RoomType(
                    name="Oranges", slug="oranges", has_variants=False
                ),
                room_models.RoomType(
                    name="Other attributes", slug="other", has_variants=False
                ),
            ]
        )
    )

    colors_attr, trademark_attr, dummy_attr = list(
        attribute_models.Attribute.objects.bulk_create(
            [
                attribute_models.Attribute(
                    name="Colors",
                    slug="colors",
                    input_type=in_multivals,
                    type=AttributeType.ROOM_TYPE,
                ),
                attribute_models.Attribute(
                    name="Trademark", slug="trademark", type=AttributeType.ROOM_TYPE
                ),
                attribute_models.Attribute(
                    name="Dummy", slug="dummy", type=AttributeType.ROOM_TYPE
                ),
            ]
        )
    )

    # Manually add every attribute to given room types
    # to force the preservation of ordering
    pt_apples.room_attributes.add(colors_attr)
    pt_apples.room_attributes.add(trademark_attr)

    pt_oranges.room_attributes.add(colors_attr)
    pt_oranges.room_attributes.add(trademark_attr)

    pt_other.room_attributes.add(dummy_attr)

    assert len(COLORS) == len(TRADEMARKS)

    apples = list(
        room_models.Room.objects.bulk_create(
            [
                room_models.Room(
                    name=f"{attrs[0]} Apple - {attrs[1]} ({i})",
                    slug=f"{attrs[0]}-apple-{attrs[1]}-({i})",
                    room_type=pt_apples,
                    category=category,
                )
                for i, attrs in enumerate(zip(COLORS, TRADEMARKS))
            ]
        )
    )
    for room_apple in apples:
        room_models.RoomChannelListing.objects.create(
            room=room_apple,
            channel=channel_USD,
            is_published=True,
            visible_in_listings=True,
        )
        variant = room_models.RoomVariant.objects.create(
            room=room_apple, sku=room_apple.slug
        )
        room_models.RoomVariantChannelListing.objects.create(
            variant=variant,
            channel=channel_USD,
            price_amount=Decimal(10),
            cost_price_amount=Decimal(1),
            currency=channel_USD.currency_code,
        )
    oranges = list(
        room_models.Room.objects.bulk_create(
            [
                room_models.Room(
                    name=f"{attrs[0]} Orange - {attrs[1]} ({i})",
                    slug=f"{attrs[0]}-orange-{attrs[1]}-({i})",
                    room_type=pt_oranges,
                    category=category,
                )
                for i, attrs in enumerate(zip(COLORS, TRADEMARKS))
            ]
        )
    )
    for room_orange in oranges:
        room_models.RoomChannelListing.objects.create(
            room=room_orange,
            channel=channel_USD,
            is_published=True,
            visible_in_listings=True,
        )
        variant = room_models.RoomVariant.objects.create(
            room=room_orange, sku=room_orange.slug
        )
        room_models.RoomVariantChannelListing.objects.create(
            variant=variant,
            channel=channel_USD,
            cost_price_amount=Decimal(1),
            price_amount=Decimal(10),
            currency=channel_USD.currency_code,
        )
    dummy = room_models.Room.objects.create(
        name="Oopsie Dummy",
        slug="oopsie-dummy",
        room_type=pt_other,
        category=category,
    )
    room_models.RoomChannelListing.objects.create(
        room=dummy,
        channel=channel_USD,
        is_published=True,
        visible_in_listings=True,
    )
    variant = room_models.RoomVariant.objects.create(
        room=dummy, sku=dummy.slug
    )
    room_models.RoomVariantChannelListing.objects.create(
        variant=variant,
        channel=channel_USD,
        cost_price_amount=Decimal(1),
        price_amount=Decimal(10),
        currency=channel_USD.currency_code,
    )
    other_dummy = room_models.Room.objects.create(
        name="Another Dummy but first in ASC and has no attribute value",
        slug="another-dummy",
        room_type=pt_other,
        category=category,
    )
    room_models.RoomChannelListing.objects.create(
        room=other_dummy,
        channel=channel_USD,
        is_published=True,
        visible_in_listings=True,
    )
    variant = room_models.RoomVariant.objects.create(
        room=other_dummy, sku=other_dummy.slug
    )
    room_models.RoomVariantChannelListing.objects.create(
        variant=variant,
        channel=channel_USD,
        cost_price_amount=Decimal(1),
        price_amount=Decimal(10),
        currency=channel_USD.currency_code,
    )
    dummy_attr_value = attr_value(dummy_attr, DUMMIES[0])
    associate_attribute_values_to_instance(dummy, dummy_attr, *dummy_attr_value)

    for rooms in (apples, oranges):
        for room, attr_values in zip(rooms, COLORS):
            attr_values = attr_value(colors_attr, *attr_values)
            associate_attribute_values_to_instance(room, colors_attr, *attr_values)

        for room, attr_values in zip(rooms, TRADEMARKS):
            attr_values = attr_value(trademark_attr, attr_values)
            associate_attribute_values_to_instance(
                room, trademark_attr, *attr_values
            )

    return colors_attr, trademark_attr, dummy_attr


def test_sort_rooms_cannot_sort_both_by_field_and_by_attribute(
    api_client, channel_USD
):
    """Ensure one cannot both sort by a supplied field and sort by a given attribute ID
    at the same time.
    """
    query = QUERY_SORT_ROOMS_BY_ATTRIBUTE
    variables = {
        "field": "NAME",
        "attributeId": "SomeAttributeId",
        "direction": "ASC",
        "channel": channel_USD.slug,
    }

    response = api_client.post_graphql(query, variables)
    response = get_graphql_content(response, ignore_errors=True)

    errors = response.get("errors", [])

    assert len(errors) == 1, response
    assert errors[0]["message"] == (
        "You must provide either `field` or `attributeId` to sort the rooms."
    )


# Ordered by the given attribute value, then by the room name.
#
# If the room doesn't have a value, it will be placed at the bottom of the rooms
# having a value and will be ordered by their room name.
#
# If the room doesn't have such attribute in its room type, it will be placed
# at the end of the other rooms having such attribute. They will be ordered by their
# name as well.
EXPECTED_SORTED_DATA_SINGLE_VALUE_ASC = [
    {
        "node": {
            "attributes": [
                {
                    "attribute": {"slug": "colors"},
                    "values": [{"name": "Blue"}, {"name": "Gray"}],
                },
                {"attribute": {"slug": "trademark"}, "values": [{"name": "A"}]},
            ],
            "name": "['Blue', 'Gray'] Apple - A (1)",
        }
    },
    {
        "node": {
            "attributes": [
                {
                    "attribute": {"slug": "colors"},
                    "values": [{"name": "Blue"}, {"name": "Gray"}],
                },
                {"attribute": {"slug": "trademark"}, "values": [{"name": "A"}]},
            ],
            "name": "['Blue', 'Gray'] Orange - A (1)",
        }
    },
    {
        "node": {
            "attributes": [
                {
                    "attribute": {"slug": "colors"},
                    "values": [{"name": "Blue"}, {"name": "Red"}],
                },
                {"attribute": {"slug": "trademark"}, "values": [{"name": "A"}]},
            ],
            "name": "['Blue', 'Red'] Apple - A (0)",
        }
    },
    {
        "node": {
            "attributes": [
                {
                    "attribute": {"slug": "colors"},
                    "values": [{"name": "Blue"}, {"name": "Red"}],
                },
                {"attribute": {"slug": "trademark"}, "values": [{"name": "A"}]},
            ],
            "name": "['Blue', 'Red'] Orange - A (0)",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "colors"}, "values": [{"name": "Pink"}]},
                {"attribute": {"slug": "trademark"}, "values": [{"name": "ab"}]},
            ],
            "name": "['Pink'] Apple - ab (2)",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "colors"}, "values": [{"name": "Pink"}]},
                {"attribute": {"slug": "trademark"}, "values": [{"name": "ab"}]},
            ],
            "name": "['Pink'] Orange - ab (2)",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "colors"}, "values": [{"name": "Pink"}]},
                {"attribute": {"slug": "trademark"}, "values": [{"name": "b"}]},
            ],
            "name": "['Pink'] Apple - b (3)",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "colors"}, "values": [{"name": "Pink"}]},
                {"attribute": {"slug": "trademark"}, "values": [{"name": "b"}]},
            ],
            "name": "['Pink'] Orange - b (3)",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "colors"}, "values": [{"name": "Green"}]},
                {"attribute": {"slug": "trademark"}, "values": [{"name": "y"}]},
            ],
            "name": "['Green'] Apple - y (4)",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "colors"}, "values": [{"name": "Green"}]},
                {"attribute": {"slug": "trademark"}, "values": [{"name": "y"}]},
            ],
            "name": "['Green'] Orange - y (4)",
        }
    },
    {
        "node": {
            "attributes": [{"attribute": {"slug": "dummy"}, "values": []}],
            "name": "Another Dummy but first in ASC and has no attribute " "value",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "dummy"}, "values": [{"name": "Oopsie"}]}
            ],
            "name": "Oopsie Dummy",
        }
    },
]

EXPECTED_SORTED_DATA_MULTIPLE_VALUES_ASC = [
    {
        "node": {
            "attributes": [
                {
                    "attribute": {"slug": "colors"},
                    "values": [{"name": "Blue"}, {"name": "Gray"}],
                },
                {"attribute": {"slug": "trademark"}, "values": [{"name": "A"}]},
            ],
            "name": "['Blue', 'Gray'] Apple - A (1)",
        }
    },
    {
        "node": {
            "attributes": [
                {
                    "attribute": {"slug": "colors"},
                    "values": [{"name": "Blue"}, {"name": "Gray"}],
                },
                {"attribute": {"slug": "trademark"}, "values": [{"name": "A"}]},
            ],
            "name": "['Blue', 'Gray'] Orange - A (1)",
        }
    },
    {
        "node": {
            "attributes": [
                {
                    "attribute": {"slug": "colors"},
                    "values": [{"name": "Blue"}, {"name": "Red"}],
                },
                {"attribute": {"slug": "trademark"}, "values": [{"name": "A"}]},
            ],
            "name": "['Blue', 'Red'] Apple - A (0)",
        }
    },
    {
        "node": {
            "attributes": [
                {
                    "attribute": {"slug": "colors"},
                    "values": [{"name": "Blue"}, {"name": "Red"}],
                },
                {"attribute": {"slug": "trademark"}, "values": [{"name": "A"}]},
            ],
            "name": "['Blue', 'Red'] Orange - A (0)",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "colors"}, "values": [{"name": "Green"}]},
                {"attribute": {"slug": "trademark"}, "values": [{"name": "y"}]},
            ],
            "name": "['Green'] Apple - y (4)",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "colors"}, "values": [{"name": "Green"}]},
                {"attribute": {"slug": "trademark"}, "values": [{"name": "y"}]},
            ],
            "name": "['Green'] Orange - y (4)",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "colors"}, "values": [{"name": "Pink"}]},
                {"attribute": {"slug": "trademark"}, "values": [{"name": "ab"}]},
            ],
            "name": "['Pink'] Apple - ab (2)",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "colors"}, "values": [{"name": "Pink"}]},
                {"attribute": {"slug": "trademark"}, "values": [{"name": "b"}]},
            ],
            "name": "['Pink'] Apple - b (3)",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "colors"}, "values": [{"name": "Pink"}]},
                {"attribute": {"slug": "trademark"}, "values": [{"name": "ab"}]},
            ],
            "name": "['Pink'] Orange - ab (2)",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "colors"}, "values": [{"name": "Pink"}]},
                {"attribute": {"slug": "trademark"}, "values": [{"name": "b"}]},
            ],
            "name": "['Pink'] Orange - b (3)",
        }
    },
    {
        "node": {
            "attributes": [{"attribute": {"slug": "dummy"}, "values": []}],
            "name": "Another Dummy but first in ASC and has no attribute " "value",
        }
    },
    {
        "node": {
            "attributes": [
                {"attribute": {"slug": "dummy"}, "values": [{"name": "Oopsie"}]}
            ],
            "name": "Oopsie Dummy",
        }
    },
]


@pytest.mark.parametrize("ascending", [True, False])
def test_sort_room_by_attribute_single_value(
    api_client, rooms_structures, ascending, channel_USD
):
    _, attribute, _ = rooms_structures
    attribute_id: str = graphene.Node.to_global_id("Attribute", attribute.pk)
    direction = "ASC" if ascending else "DESC"

    query = QUERY_SORT_ROOMS_BY_ATTRIBUTE
    variables = {
        "attributeId": attribute_id,
        "direction": direction,
        "channel": channel_USD.slug,
    }

    response = get_graphql_content(api_client.post_graphql(query, variables))
    rooms = response["data"]["rooms"]["edges"]

    assert len(rooms) == room_models.Room.objects.count()

    if ascending:
        assert rooms == EXPECTED_SORTED_DATA_SINGLE_VALUE_ASC
    else:
        assert rooms == list(reversed(EXPECTED_SORTED_DATA_SINGLE_VALUE_ASC))


@pytest.mark.parametrize("ascending", [True, False])
def test_sort_room_by_attribute_multiple_values(
    api_client, rooms_structures, ascending, channel_USD
):
    attribute, _, _ = rooms_structures
    attribute_id: str = graphene.Node.to_global_id("Attribute", attribute.pk)
    direction = "ASC" if ascending else "DESC"

    query = QUERY_SORT_ROOMS_BY_ATTRIBUTE
    variables = {
        "attributeId": attribute_id,
        "direction": direction,
        "channel": channel_USD.slug,
    }

    response = get_graphql_content(api_client.post_graphql(query, variables))
    rooms = response["data"]["rooms"]["edges"]

    assert len(rooms) == room_models.Room.objects.count()

    if ascending:
        assert rooms == EXPECTED_SORTED_DATA_MULTIPLE_VALUES_ASC
    else:
        assert rooms == list(reversed(EXPECTED_SORTED_DATA_MULTIPLE_VALUES_ASC))


def test_sort_room_not_having_attribute_data(api_client, category, count_queries):
    """Test the case where a room has a given attribute assigned to their
    room type but no attribute data assigned, i.e. the room's PT was changed
    after the room creation.
    """
    expected_results = ["Z", "Y", "A"]
    room_create_kwargs = {"category": category}

    # Create two room types, with one forced to be at the bottom (no such attribute)
    room_type = room_models.RoomType.objects.create(
        name="Apples", slug="apples"
    )
    other_room_type = room_models.RoomType.objects.create(
        name="Chocolates", slug="chocolates"
    )

    # Assign an attribute to the room type
    attribute = attribute_models.Attribute.objects.create(
        name="Kind", slug="kind", type=AttributeType.ROOM_TYPE
    )
    value = attribute_models.AttributeValue.objects.create(
        name="Value", slug="value", attribute=attribute
    )
    room_type.room_attributes.add(attribute)

    # Create a room with a value
    room_having_attr_value = room_models.Room.objects.create(
        name="Z", slug="z", room_type=room_type, **room_create_kwargs
    )
    associate_attribute_values_to_instance(room_having_attr_value, attribute, value)

    # Create a room having the same room type but no attribute data
    room_models.Room.objects.create(
        name="Y", slug="y", room_type=room_type, **room_create_kwargs
    )

    # Create a new room having a name that would be ordered first in ascending
    # as the default ordering is by name for non matching rooms
    room_models.Room.objects.create(
        name="A", slug="a", room_type=other_room_type, **room_create_kwargs
    )

    # Sort the rooms
    qs = room_models.Room.objects.sort_by_attribute(attribute_pk=attribute.pk)
    qs = qs.values_list("name", flat=True)

    # Compare the results
    sorted_results = list(qs)
    assert sorted_results == expected_results


@pytest.mark.parametrize(
    "attribute_id",
    [
        "",
        graphene.Node.to_global_id("Attribute", "not a number"),
        graphene.Node.to_global_id("Attribute", -1),
    ],
)
def test_sort_room_by_attribute_using_invalid_attribute_id(
    api_client, room_list_published, attribute_id, channel_USD
):
    """Ensure passing an empty attribute ID as sorting field does nothing."""

    query = QUERY_SORT_ROOMS_BY_ATTRIBUTE

    # Rooms are ordered in descending order to ensure we
    # are not actually trying to sort them at all
    variables = {
        "attributeId": attribute_id,
        "direction": "DESC",
        "channel": channel_USD.slug,
    }

    response = get_graphql_content(api_client.post_graphql(query, variables))
    rooms = response["data"]["rooms"]["edges"]

    assert len(rooms) == room_models.Room.objects.count()
    assert rooms[0]["node"]["name"] == room_models.Room.objects.first().name


@pytest.mark.parametrize("direction", ["ASC", "DESC"])
def test_sort_room_by_attribute_using_attribute_having_no_rooms(
    api_client, room_list_published, direction, channel_USD
):
    """Ensure passing an empty attribute ID as sorting field does nothing."""

    query = QUERY_SORT_ROOMS_BY_ATTRIBUTE
    attribute_without_rooms = attribute_models.Attribute.objects.create(
        name="Colors 2", slug="colors-2", type=AttributeType.ROOM_TYPE
    )

    attribute_id: str = graphene.Node.to_global_id(
        "Attribute", attribute_without_rooms.pk
    )
    variables = {
        "attributeId": attribute_id,
        "direction": direction,
        "channel": channel_USD.slug,
    }

    response = get_graphql_content(api_client.post_graphql(query, variables))
    rooms = response["data"]["rooms"]["edges"]

    if direction == "ASC":
        expected_first_room = room_models.Room.objects.order_by("slug").first()
    else:
        expected_first_room = room_models.Room.objects.order_by("slug").last()

    assert len(rooms) == room_models.Room.objects.count()
    assert rooms[0]["node"]["name"] == expected_first_room.name
