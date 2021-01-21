from unittest import mock

import graphene
import pytest

from ....attribute import AttributeInputType, AttributeType
from ....attribute.models import (
    Attribute,
    AttributeRoom,
    AttributeValue,
    AttributeVariant,
)
from ....room.error_codes import RoomErrorCode
from ....room.models import RoomType
from ...attribute.enums import AttributeTypeEnum
from ...core.utils import snake_to_camel_case
from ...tests.utils import get_graphql_content
from ..enums import RoomAttributeType

QUERY_ROOM_AND_VARIANTS_ATTRIBUTES = """
    query ($channel: String){
      rooms(first: 1, channel: $channel) {
        edges {
          node {
            attributes {
              attribute {
                slug
                type
              }
              values {
                slug
              }
            }
            variants {
              attributes {
                attribute {
                  slug
                  type
                }
                values {
                  slug
                }
              }
            }
          }
        }
      }
    }
"""


@pytest.mark.parametrize("is_staff", (False, True))
def test_resolve_attributes_with_hidden(
    user_api_client,
    staff_api_client,
    room,
    color_attribute,
    size_attribute,
    is_staff,
    permission_manage_rooms,
    channel_USD,
):
    """Ensure non-staff users don't see hidden attributes, and staff users having
    the 'manage room' permission can.
    """
    variables = {"channel": channel_USD.slug}
    query = QUERY_ROOM_AND_VARIANTS_ATTRIBUTES
    api_client = user_api_client

    variant = room.variants.first()

    room_attribute = color_attribute
    variant_attribute = size_attribute

    expected_room_attribute_count = room.attributes.count() - 1
    expected_variant_attribute_count = variant.attributes.count() - 1

    if is_staff:
        api_client = staff_api_client
        api_client.user.user_permissions.add(permission_manage_rooms)
        expected_room_attribute_count += 1
        expected_variant_attribute_count += 1

    # Hide one room and variant attribute from the storefront
    for attribute in (room_attribute, variant_attribute):
        attribute.visible_in_storefront = False
        attribute.save(update_fields=["visible_in_storefront"])

    room = get_graphql_content(api_client.post_graphql(query, variables))["data"][
        "rooms"
    ]["edges"][0]["node"]

    assert len(room["attributes"]) == expected_room_attribute_count
    assert len(room["variants"][0]["attributes"]) == expected_variant_attribute_count


def test_resolve_attribute_values(user_api_client, room, staff_user, channel_USD):
    """Ensure the attribute values are properly resolved."""
    variables = {"channel": channel_USD.slug}
    query = QUERY_ROOM_AND_VARIANTS_ATTRIBUTES
    api_client = user_api_client

    variant = room.variants.first()

    assert room.attributes.count() == 1
    assert variant.attributes.count() == 1

    room_attribute_values = list(
        room.attributes.first().values.values_list("slug", flat=True)
    )
    variant_attribute_values = list(
        variant.attributes.first().values.values_list("slug", flat=True)
    )

    assert len(room_attribute_values) == 1
    assert len(variant_attribute_values) == 1

    room = get_graphql_content(api_client.post_graphql(query, variables))["data"][
        "rooms"
    ]["edges"][0]["node"]

    room_attributes = room["attributes"]
    variant_attributes = room["variants"][0]["attributes"]

    assert len(room_attributes) == len(room_attribute_values)
    assert len(variant_attributes) == len(variant_attribute_values)

    assert room_attributes[0]["attribute"]["slug"] == "color"
    assert (
        room_attributes[0]["attribute"]["type"]
        == AttributeTypeEnum.ROOM_TYPE.name
    )
    assert room_attributes[0]["values"][0]["slug"] == room_attribute_values[0]

    assert variant_attributes[0]["attribute"]["slug"] == "size"
    assert (
        variant_attributes[0]["attribute"]["type"]
        == AttributeTypeEnum.ROOM_TYPE.name
    )


def test_resolve_attribute_values_non_assigned_to_node(
    user_api_client, room, staff_user, channel_USD
):
    """Ensure the attribute values are properly resolved when an attribute is part
    of the room type but not of the node (room/variant), thus no values should be
    resolved.
    """
    variables = {"channel": channel_USD.slug}
    query = QUERY_ROOM_AND_VARIANTS_ATTRIBUTES
    api_client = user_api_client

    variant = room.variants.first()
    room_type = room.room_type

    # Create dummy attributes
    unassigned_room_attribute = Attribute.objects.create(
        name="P", slug="room", type=AttributeType.ROOM_TYPE
    )
    unassigned_variant_attribute = Attribute.objects.create(
        name="V", slug="variant", type=AttributeType.ROOM_TYPE
    )

    # Create a value for each dummy attribute to ensure they are not returned
    # by the room or variant as they are not associated to them
    AttributeValue.objects.bulk_create(
        [
            AttributeValue(slug="a", name="A", attribute=unassigned_room_attribute),
            AttributeValue(slug="b", name="B", attribute=unassigned_room_attribute),
        ]
    )

    # Assign the dummy attributes to the room type and push them at the top
    # through a sort_order=0 as the other attributes have sort_order=null
    AttributeRoom.objects.create(
        attribute=unassigned_room_attribute, room_type=room_type, sort_order=0
    )
    AttributeVariant.objects.create(
        attribute=unassigned_variant_attribute, room_type=room_type, sort_order=0
    )

    assert room.attributes.count() == 1
    assert variant.attributes.count() == 1

    room = get_graphql_content(api_client.post_graphql(query, variables))["data"][
        "rooms"
    ]["edges"][0]["node"]

    room_attributes = room["attributes"]
    variant_attributes = room["variants"][0]["attributes"]

    assert len(room_attributes) == 2, "Non-assigned attr from the PT may be missing"
    assert len(variant_attributes) == 2, "Non-assigned attr from the PT may be missing"

    assert room_attributes[0]["attribute"]["slug"] == "room"
    assert room_attributes[0]["values"] == []

    assert variant_attributes[0]["attribute"]["slug"] == "variant"
    assert variant_attributes[0]["values"] == []


def test_resolve_assigned_attribute_without_values(
    api_client, room_type, room, channel_USD
):
    """Ensure the attributes assigned to a room type are resolved even if
    the room doesn't provide any value for it or is not directly associated to it.
    """
    # Retrieve the room's variant
    variant = room.variants.get()

    # Remove all attributes and values from the room and its variant
    room.attributesrelated.clear()
    variant.attributesrelated.clear()

    # Retrieve the room and variant's attributes
    rooms = get_graphql_content(
        api_client.post_graphql(
            """
        query ($channel: String) {
          rooms(first: 10, channel: $channel) {
            edges {
              node {
                attributes {
                  attribute {
                    slug
                  }
                  values {
                    name
                  }
                }
                variants {
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
        }
    """,
            {"channel": channel_USD.slug},
        )
    )["data"]["rooms"]["edges"]

    # Ensure we are only working on one room and variant, the ones we are testing
    assert len(rooms) == 1
    assert len(rooms[0]["node"]["variants"]) == 1

    # Retrieve the nodes data
    room = rooms[0]["node"]
    variant = room["variants"][0]

    # Ensure the room attributes values are all None
    assert len(room["attributes"]) == 1
    assert room["attributes"][0]["attribute"]["slug"] == "color"
    assert room["attributes"][0]["values"] == []

    # Ensure the variant attributes values are all None
    assert variant["attributes"][0]["attribute"]["slug"] == "size"
    assert variant["attributes"][0]["values"] == []


ROOM_ASSIGN_ATTR_QUERY = """
    mutation assign($roomTypeId: ID!, $operations: [RoomAttributeAssignInput]!) {
      roomAttributeAssign(roomTypeId: $roomTypeId, operations: $operations) {
        roomErrors {
          field
          code
          message
          attributes
        }
        roomType {
          id
          roomAttributes {
            id
          }
          variantAttributes {
            id
          }
        }
      }
    }
"""


def test_assign_attributes_to_room_type(
    staff_api_client,
    permission_manage_room_types_and_attributes,
    room_type_attribute_list,
):
    room_type = RoomType.objects.create(name="Default Type", has_variants=True)
    room_type_global_id = graphene.Node.to_global_id("RoomType", room_type.pk)

    query = ROOM_ASSIGN_ATTR_QUERY
    operations = []
    variables = {"roomTypeId": room_type_global_id, "operations": operations}

    room_attributes_ids = {attr.pk for attr in room_type_attribute_list[:2]}
    variant_attributes_ids = {attr.pk for attr in room_type_attribute_list[2:]}

    for attr_id in room_attributes_ids:
        operations.append(
            {"type": "ROOM", "id": graphene.Node.to_global_id("Attribute", attr_id)}
        )

    for attr_id in variant_attributes_ids:
        operations.append(
            {"type": "VARIANT", "id": graphene.Node.to_global_id("Attribute", attr_id)}
        )

    content = get_graphql_content(
        staff_api_client.post_graphql(
            query,
            variables,
            permissions=[permission_manage_room_types_and_attributes],
        )
    )["data"]["roomAttributeAssign"]
    assert not content["roomErrors"], "Should have succeeded"

    assert content["roomType"]["id"] == room_type_global_id
    assert len(content["roomType"]["roomAttributes"]) == len(
        room_attributes_ids
    )
    assert len(content["roomType"]["variantAttributes"]) == len(
        variant_attributes_ids
    )

    found_room_attrs_ids = {
        int(graphene.Node.from_global_id(attr["id"])[1])
        for attr in content["roomType"]["roomAttributes"]
    }
    found_variant_attrs_ids = {
        int(graphene.Node.from_global_id(attr["id"])[1])
        for attr in content["roomType"]["variantAttributes"]
    }

    assert found_room_attrs_ids == room_attributes_ids
    assert found_variant_attrs_ids == variant_attributes_ids


def test_assign_non_existing_attributes_to_room_type(
    staff_api_client,
    permission_manage_room_types_and_attributes,
    room_type_attribute_list,
):
    room_type = RoomType.objects.create(name="Default Type", has_variants=True)
    room_type_global_id = graphene.Node.to_global_id("RoomType", room_type.pk)

    query = ROOM_ASSIGN_ATTR_QUERY
    attribute_id = graphene.Node.to_global_id("Attribute", "55511155593")
    operations = [{"type": "ROOM", "id": attribute_id}]
    variables = {"roomTypeId": room_type_global_id, "operations": operations}

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)
    content = content["data"]["roomAttributeAssign"]
    assert content["roomErrors"][0]["code"] == RoomErrorCode.NOT_FOUND.name
    assert content["roomErrors"][0]["field"] == "operations"
    assert content["roomErrors"][0]["attributes"] == [attribute_id]


def test_assign_variant_attribute_to_room_type_with_disabled_variants(
    staff_api_client,
    permission_manage_room_types_and_attributes,
    room_type_without_variant,
    color_attribute_without_values,
):
    """The assignAttribute mutation should raise an error when trying
    to add an attribute as a variant attribute when
    the room type doesn't support variants"""

    room_type = room_type_without_variant
    attribute = color_attribute_without_values
    staff_api_client.user.user_permissions.add(
        permission_manage_room_types_and_attributes
    )

    room_type_global_id = graphene.Node.to_global_id("RoomType", room_type.pk)

    query = ROOM_ASSIGN_ATTR_QUERY
    operations = [
        {"type": "VARIANT", "id": graphene.Node.to_global_id("Attribute", attribute.pk)}
    ]
    variables = {"roomTypeId": room_type_global_id, "operations": operations}

    content = get_graphql_content(staff_api_client.post_graphql(query, variables))[
        "data"
    ]["roomAttributeAssign"]
    assert content["roomErrors"][0]["field"] == "operations"
    assert (
        content["roomErrors"][0]["message"]
        == "Variants are disabled in this room type."
    )
    assert (
        content["roomErrors"][0]["code"]
        == RoomErrorCode.ATTRIBUTE_VARIANTS_DISABLED.name
    )


def test_assign_variant_attribute_having_multiselect_input_type(
    staff_api_client,
    permission_manage_room_types_and_attributes,
    room_type,
    size_attribute,
):
    """The assignAttribute mutation should raise an error when trying
    to use an attribute as a variant attribute when
    the attribute's input type doesn't support variants"""

    attribute = size_attribute
    attribute.input_type = AttributeInputType.MULTISELECT
    attribute.save(update_fields=["input_type"])
    room_type.variant_attributes.clear()

    staff_api_client.user.user_permissions.add(
        permission_manage_room_types_and_attributes
    )

    room_type_global_id = graphene.Node.to_global_id("RoomType", room_type.pk)
    attr_id = graphene.Node.to_global_id("Attribute", attribute.pk)

    query = ROOM_ASSIGN_ATTR_QUERY
    operations = [{"type": "VARIANT", "id": attr_id}]
    variables = {"roomTypeId": room_type_global_id, "operations": operations}

    content = get_graphql_content(staff_api_client.post_graphql(query, variables))[
        "data"
    ]["roomAttributeAssign"]
    assert not content["roomErrors"]
    assert content["roomType"]["id"] == room_type_global_id
    assert len(content["roomType"]["variantAttributes"]) == 1
    assert content["roomType"]["variantAttributes"][0]["id"] == attr_id


@pytest.mark.parametrize(
    "room_type_attribute_type, gql_attribute_type",
    (
        (RoomAttributeType.ROOM, RoomAttributeType.VARIANT),
        (RoomAttributeType.VARIANT, RoomAttributeType.ROOM),
        (RoomAttributeType.ROOM, RoomAttributeType.ROOM),
        (RoomAttributeType.VARIANT, RoomAttributeType.VARIANT),
    ),
)
def test_assign_attribute_to_room_type_having_already_that_attribute(
    staff_api_client,
    permission_manage_room_types_and_attributes,
    color_attribute_without_values,
    room_type_attribute_type,
    gql_attribute_type,
):
    """The assignAttribute mutation should raise an error when trying
    to add an attribute already contained in the room type."""

    room_type = RoomType.objects.create(name="Type")
    attribute = color_attribute_without_values
    staff_api_client.user.user_permissions.add(
        permission_manage_room_types_and_attributes
    )

    room_type_global_id = graphene.Node.to_global_id("RoomType", room_type.pk)

    if room_type_attribute_type == RoomAttributeType.ROOM:
        room_type.room_attributes.add(attribute)
    elif room_type_attribute_type == RoomAttributeType.VARIANT:
        room_type.variant_attributes.add(attribute)
    else:
        raise ValueError(f"Unknown: {room_type}")

    query = ROOM_ASSIGN_ATTR_QUERY
    operations = [
        {
            "type": gql_attribute_type.value,
            "id": graphene.Node.to_global_id("Attribute", attribute.pk),
        }
    ]
    variables = {"roomTypeId": room_type_global_id, "operations": operations}

    content = get_graphql_content(staff_api_client.post_graphql(query, variables))[
        "data"
    ]["roomAttributeAssign"]
    assert content["roomErrors"][0]["field"] == "operations"
    assert (
        content["roomErrors"][0]["message"]
        == "Color (color) have already been assigned to this room type."
    )
    assert (
        content["roomErrors"][0]["code"]
        == RoomErrorCode.ATTRIBUTE_ALREADY_ASSIGNED.name
    )


def test_assign_page_attribute_to_room_type(
    staff_api_client,
    permission_manage_room_types_and_attributes,
    tag_page_attribute,
    room_type,
):
    # given
    staff_api_client.user.user_permissions.add(
        permission_manage_room_types_and_attributes
    )

    tag_page_attr_id = graphene.Node.to_global_id("Attribute", tag_page_attribute.pk)

    variables = {
        "roomTypeId": graphene.Node.to_global_id("RoomType", room_type.pk),
        "operations": [
            {"type": RoomAttributeType.ROOM.value, "id": tag_page_attr_id},
        ],
    }

    # when
    response = staff_api_client.post_graphql(ROOM_ASSIGN_ATTR_QUERY, variables)

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomAttributeAssign"]
    errors = data["roomErrors"]

    assert not data["roomType"]
    assert len(errors) == 1
    assert errors[0]["field"] == "operations"
    assert errors[0]["code"] == RoomErrorCode.INVALID.name
    assert errors[0]["attributes"] == [tag_page_attr_id]


def test_assign_attribute_to_room_type_multiply_errors_returned(
    staff_api_client,
    permission_manage_room_types_and_attributes,
    color_attribute,
    size_attribute,
    tag_page_attribute,
):
    # given
    room_type = RoomType.objects.create(name="Type")
    staff_api_client.user.user_permissions.add(
        permission_manage_room_types_and_attributes
    )

    room_type.room_attributes.add(color_attribute)

    unsupported_type_attr = size_attribute
    unsupported_type_attr.input_type = AttributeInputType.MULTISELECT
    unsupported_type_attr.save(update_fields=["input_type"])

    color_attr_id = graphene.Node.to_global_id("Attribute", color_attribute.pk)
    unsupported_type_attr_id = graphene.Node.to_global_id(
        "Attribute", unsupported_type_attr.pk
    )
    tag_page_attr_id = graphene.Node.to_global_id("Attribute", tag_page_attribute.pk)

    variables = {
        "roomTypeId": graphene.Node.to_global_id("RoomType", room_type.pk),
        "operations": [
            {"type": RoomAttributeType.ROOM.value, "id": color_attr_id},
            {
                "type": RoomAttributeType.VARIANT.value,
                "id": unsupported_type_attr_id,
            },
            {"type": RoomAttributeType.ROOM.value, "id": tag_page_attr_id},
        ],
    }

    # when
    response = staff_api_client.post_graphql(ROOM_ASSIGN_ATTR_QUERY, variables)

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomAttributeAssign"]
    errors = data["roomErrors"]

    assert not data["roomType"]
    assert len(errors) == 2
    expected_errors = [
        {
            "code": RoomErrorCode.ATTRIBUTE_ALREADY_ASSIGNED.name,
            "field": "operations",
            "message": mock.ANY,
            "attributes": [color_attr_id],
        },
        {
            "code": RoomErrorCode.INVALID.name,
            "field": "operations",
            "message": mock.ANY,
            "attributes": [tag_page_attr_id],
        },
    ]
    for error in expected_errors:
        assert error in errors


ROOM_UNASSIGN_ATTR_QUERY = """
    mutation RoomUnassignAttribute(
      $roomTypeId: ID!, $attributeIds: [ID]!
    ) {
      roomAttributeUnassign(
          roomTypeId: $roomTypeId, attributeIds: $attributeIds
      ) {
        roomErrors {
          field
          message
        }
        roomType {
          id
          variantAttributes {
            id
          }
          roomAttributes {
            id
          }
        }
      }
    }
"""


def test_unassign_attributes_from_room_type(
    staff_api_client,
    permission_manage_room_types_and_attributes,
    room_type_attribute_list,
):
    room_type = RoomType.objects.create(name="Type")
    room_type_global_id = graphene.Node.to_global_id("RoomType", room_type.pk)

    variant_attribute, *room_attributes = room_type_attribute_list
    room_type.room_attributes.add(*room_attributes)
    room_type.variant_attributes.add(variant_attribute)

    remaining_attribute_global_id = graphene.Node.to_global_id(
        "Attribute", room_attributes[1].pk
    )

    query = ROOM_UNASSIGN_ATTR_QUERY
    variables = {
        "roomTypeId": room_type_global_id,
        "attributeIds": [
            graphene.Node.to_global_id("Attribute", room_attributes[0].pk)
        ],
    }

    content = get_graphql_content(
        staff_api_client.post_graphql(
            query,
            variables,
            permissions=[permission_manage_room_types_and_attributes],
        )
    )["data"]["roomAttributeUnassign"]
    assert not content["roomErrors"]

    assert content["roomType"]["id"] == room_type_global_id
    assert len(content["roomType"]["roomAttributes"]) == 1
    assert len(content["roomType"]["variantAttributes"]) == 1

    assert (
        content["roomType"]["roomAttributes"][0]["id"]
        == remaining_attribute_global_id
    )


def test_unassign_attributes_not_in_room_type(
    staff_api_client,
    permission_manage_room_types_and_attributes,
    color_attribute_without_values,
):
    """The unAssignAttribute mutation should not raise any error when trying
    to remove an attribute that is not/no longer in the room type."""

    staff_api_client.user.user_permissions.add(
        permission_manage_room_types_and_attributes
    )

    room_type = RoomType.objects.create(name="Type")
    room_type_global_id = graphene.Node.to_global_id("RoomType", room_type.pk)

    query = ROOM_UNASSIGN_ATTR_QUERY
    variables = {
        "roomTypeId": room_type_global_id,
        "attributeIds": [
            graphene.Node.to_global_id("Attribute", color_attribute_without_values.pk)
        ],
    }

    content = get_graphql_content(staff_api_client.post_graphql(query, variables))[
        "data"
    ]["roomAttributeUnassign"]
    assert not content["roomErrors"]

    assert content["roomType"]["id"] == room_type_global_id
    assert len(content["roomType"]["roomAttributes"]) == 0
    assert len(content["roomType"]["variantAttributes"]) == 0


def test_retrieve_room_attributes_input_type(
    staff_api_client, room, permission_manage_rooms, channel_USD
):
    query = """
        query ($channel: String){
          rooms(first: 10, channel: $channel) {
            edges {
              node {
                attributes {
                  values {
                    type
                    inputType
                  }
                }
              }
            }
          }
        }
    """

    variables = {"channel": channel_USD.slug}
    found_rooms = get_graphql_content(
        staff_api_client.post_graphql(
            query, variables, permissions=[permission_manage_rooms]
        )
    )["data"]["rooms"]["edges"]
    assert len(found_rooms) == 1

    for gql_attr in found_rooms[0]["node"]["attributes"]:
        assert len(gql_attr["values"]) == 1
        assert gql_attr["values"][0]["type"] == "STRING"
        assert gql_attr["values"][0]["inputType"] == "DROPDOWN"


ATTRIBUTES_RESORT_QUERY = """
    mutation RoomTypeReorderAttributes(
      $roomTypeId: ID!
      $moves: [ReorderInput]!
      $type: RoomAttributeType!
    ) {
      roomTypeReorderAttributes(
        roomTypeId: $roomTypeId
        moves: $moves
        type: $type
      ) {
        roomType {
          id
          variantAttributes {
            id
            slug
          }
          roomAttributes {
            id
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


def test_sort_attributes_within_room_type_invalid_room_type(
    staff_api_client, permission_manage_room_types_and_attributes
):
    """Try to reorder an invalid room type (invalid ID)."""

    room_type_id = graphene.Node.to_global_id("RoomType", -1)
    attribute_id = graphene.Node.to_global_id("Attribute", -1)

    variables = {
        "type": "VARIANT",
        "roomTypeId": room_type_id,
        "moves": [{"id": attribute_id, "sortOrder": 1}],
    }

    content = get_graphql_content(
        staff_api_client.post_graphql(
            ATTRIBUTES_RESORT_QUERY,
            variables,
            permissions=[permission_manage_room_types_and_attributes],
        )
    )["data"]["roomTypeReorderAttributes"]

    assert content["roomErrors"] == [
        {
            "field": "roomTypeId",
            "code": RoomErrorCode.NOT_FOUND.name,
            "message": f"Couldn't resolve to a room type: {room_type_id}",
            "attributes": None,
        }
    ]


def test_sort_attributes_within_room_type_invalid_id(
    staff_api_client, permission_manage_room_types_and_attributes, color_attribute
):
    """Try to reorder an attribute not associated to the given room type."""

    room_type = RoomType.objects.create(name="Dummy Type")
    room_type_id = graphene.Node.to_global_id("RoomType", room_type.id)

    attribute_id = graphene.Node.to_global_id("Attribute", color_attribute.id)

    variables = {
        "type": "VARIANT",
        "roomTypeId": room_type_id,
        "moves": [{"id": attribute_id, "sortOrder": 1}],
    }

    content = get_graphql_content(
        staff_api_client.post_graphql(
            ATTRIBUTES_RESORT_QUERY,
            variables,
            permissions=[permission_manage_room_types_and_attributes],
        )
    )["data"]["roomTypeReorderAttributes"]

    assert content["roomErrors"] == [
        {
            "field": "moves",
            "message": "Couldn't resolve to an attribute.",
            "attributes": [attribute_id],
            "code": RoomErrorCode.NOT_FOUND.name,
        }
    ]


@pytest.mark.parametrize(
    "attribute_type, relation_field, backref_field",
    (
        ("VARIANT", "variant_attributes", "attributevariant"),
        ("ROOM", "room_attributes", "attributeroom"),
    ),
)
def test_sort_attributes_within_room_type(
    staff_api_client,
    room_type_attribute_list,
    permission_manage_room_types_and_attributes,
    attribute_type,
    relation_field,
    backref_field,
):
    attributes = room_type_attribute_list
    assert len(attributes) == 3

    staff_api_client.user.user_permissions.add(
        permission_manage_room_types_and_attributes
    )

    room_type = RoomType.objects.create(name="Dummy Type")
    room_type_id = graphene.Node.to_global_id("RoomType", room_type.id)
    m2m_attributes = getattr(room_type, relation_field)
    m2m_attributes.set(attributes)

    sort_method = getattr(m2m_attributes, f"{relation_field}_sorted")
    attributes = list(sort_method())

    assert len(attributes) == 3

    variables = {
        "type": attribute_type,
        "roomTypeId": room_type_id,
        "moves": [
            {
                "id": graphene.Node.to_global_id("Attribute", attributes[0].pk),
                "sortOrder": +1,
            },
            {
                "id": graphene.Node.to_global_id("Attribute", attributes[2].pk),
                "sortOrder": -1,
            },
        ],
    }

    expected_order = [attributes[1].pk, attributes[2].pk, attributes[0].pk]

    content = get_graphql_content(
        staff_api_client.post_graphql(ATTRIBUTES_RESORT_QUERY, variables)
    )["data"]["roomTypeReorderAttributes"]
    assert not content["roomErrors"]

    assert (
        content["roomType"]["id"] == room_type_id
    ), "Did not return the correct room type"

    gql_attributes = content["roomType"][snake_to_camel_case(relation_field)]
    assert len(gql_attributes) == len(expected_order)

    for attr, expected_pk in zip(gql_attributes, expected_order):
        gql_type, gql_attr_id = graphene.Node.from_global_id(attr["id"])
        assert gql_type == "Attribute"
        assert int(gql_attr_id) == expected_pk
