import graphene
import pytest

from ....attribute.models import AttributeValue
from ....attribute.utils import (
    _associate_attribute_to_instance,
    associate_attribute_values_to_instance,
)
from ...tests.utils import assert_graphql_error_with_message, get_graphql_content
from ..enums import VariantAttributeScope

VARIANT_QUERY = """
query variant(
    $id: ID, $sku: String, $variantSelection: VariantAttributeScope, $channel: String
){
    roomVariant(id:$id, sku:$sku, channel: $channel){
        sku
        attributes(variantSelection: $variantSelection) {
            attribute {
                slug
            }
            values {
                id
                slug
            }
        }
    }
}
"""


def test_get_variant_without_id_and_sku(staff_api_client, permission_manage_rooms):
    # given

    # when
    response = staff_api_client.post_graphql(
        VARIANT_QUERY,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    assert_graphql_error_with_message(
        response, "At least one of arguments is required: 'id', 'sku'."
    )


def test_get_variant_with_id_and_sku(staff_api_client, permission_manage_rooms):
    # given
    variables = {"id": "ID", "sku": "sku"}

    # when
    response = staff_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    assert_graphql_error_with_message(
        response, "Argument 'id' cannot be combined with 'sku'"
    )


def test_get_unpublished_variant_by_id_as_staff(
    staff_api_client, permission_manage_rooms, unavailable_room_with_variant
):
    # given
    variant = unavailable_room_with_variant.variants.first()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id}

    # when
    response = staff_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku


def test_get_unpublished_variant_by_id_as_app(
    app_api_client, permission_manage_rooms, unavailable_room_with_variant
):
    # given
    variant = unavailable_room_with_variant.variants.first()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id}

    # when
    response = app_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku


def test_get_unpublished_variant_by_id_as_customer(
    user_api_client, unavailable_room_with_variant, channel_USD
):
    # given
    variant = unavailable_room_with_variant.variants.first()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id, "channel": channel_USD.slug}

    # when
    response = user_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    assert not content["data"]["roomVariant"]


def test_get_unpublished_variant_by_id_as_anonymous_user(
    api_client, unavailable_room_with_variant, channel_USD
):
    # given
    variant = unavailable_room_with_variant.variants.first()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id, "channel": channel_USD.slug}

    # when
    response = api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    assert not content["data"]["roomVariant"]


def test_get_variant_by_id_as_staff(
    staff_api_client, permission_manage_rooms, variant
):
    # given
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id}

    # when
    response = staff_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku


def test_get_variant_by_id_as_app(app_api_client, permission_manage_rooms, variant):
    # given
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id}

    # when
    response = app_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku


def test_get_variant_by_id_as_customer(user_api_client, variant, channel_USD):
    # given
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id, "channel": channel_USD.slug}

    # when
    response = user_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku


def test_get_variant_by_id_as_anonymous_user(api_client, variant, channel_USD):
    # given
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id, "channel": channel_USD.slug}

    # when
    response = api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku


def test_get_unpublished_variant_by_sku_as_staff(
    staff_api_client, permission_manage_rooms, unavailable_room_with_variant
):
    # given
    variant = unavailable_room_with_variant.variants.first()
    variables = {"sku": variant.sku}

    # when
    response = staff_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku


def test_get_unpublished_variant_by_sku_as_app(
    app_api_client, permission_manage_rooms, unavailable_room_with_variant
):
    # given
    variant = unavailable_room_with_variant.variants.first()
    variables = {"sku": variant.sku}

    # when
    response = app_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku


def test_get_unpublished_variant_by_sku_as_customer(
    user_api_client, unavailable_room_with_variant, channel_USD
):
    # given
    variant = unavailable_room_with_variant.variants.first()
    variables = {"sku": variant.sku, "channel": channel_USD.slug}

    # when
    response = user_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    assert not content["data"]["roomVariant"]


def test_get_unpublished_variant_by_sku_as_anonymous_user(
    api_client, unavailable_room_with_variant, channel_USD
):
    # given
    variant = unavailable_room_with_variant.variants.first()
    variables = {"sku": variant.sku, "channel": channel_USD.slug}

    # when
    response = api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    assert not content["data"]["roomVariant"]


def test_get_variant_by_sku_as_staff(
    staff_api_client, permission_manage_rooms, variant
):
    # given
    variables = {"sku": variant.sku}

    # when
    response = staff_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku


def test_get_variant_by_sku_as_app(app_api_client, permission_manage_rooms, variant):
    # given
    variables = {"sku": variant.sku}

    # when
    response = app_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku


def test_get_variant_by_sku_as_customer(user_api_client, variant, channel_USD):
    # given
    variables = {"sku": variant.sku, "channel": channel_USD.slug}

    # when
    response = user_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku


def test_get_variant_by_sku_as_anonymous_user(api_client, variant, channel_USD):
    # given
    variables = {"sku": variant.sku, "channel": channel_USD.slug}

    # when
    response = api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku


@pytest.mark.parametrize(
    "variant_selection",
    [
        VariantAttributeScope.ALL.name,
        VariantAttributeScope.VARIANT_SELECTION.name,
        VariantAttributeScope.NOT_VARIANT_SELECTION.name,
    ],
)
def test_get_variant_by_id_with_variant_selection_filter(
    variant_selection,
    staff_api_client,
    permission_manage_rooms,
    variant,
    size_attribute,
    file_attribute_with_file_input_type_without_values,
    room_type,
):
    # given
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id, "variantSelection": variant_selection}

    room_type.variant_attributes.add(
        file_attribute_with_file_input_type_without_values
    )

    _associate_attribute_to_instance(
        variant, file_attribute_with_file_input_type_without_values.pk
    )
    _associate_attribute_to_instance(variant, size_attribute.pk)

    # when
    response = staff_api_client.post_graphql(
        VARIANT_QUERY,
        variables,
        permissions=[permission_manage_rooms],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert data["sku"] == variant.sku
    if variant_selection == VariantAttributeScope.NOT_VARIANT_SELECTION.name:
        assert len(data["attributes"]) == 1
        assert (
            data["attributes"][0]["attribute"]["slug"]
            == file_attribute_with_file_input_type_without_values.slug
        )
    elif variant_selection == VariantAttributeScope.VARIANT_SELECTION.name:
        assert len(data["attributes"]) == 1
        assert data["attributes"][0]["attribute"]["slug"] == size_attribute.slug
    else:
        len(data["attributes"]) == 2


def test_get_variant_with_sorted_attribute_values(
    staff_api_client,
    variant,
    room_type_room_reference_attribute,
    permission_manage_rooms,
    room_list,
):
    # given
    room_type = variant.room.room_type
    room_type.variant_attributes.set([room_type_room_reference_attribute])

    attr_value_1 = AttributeValue.objects.create(
        attribute=room_type_room_reference_attribute,
        name=room_list[0].name,
        slug=f"{variant.pk}_{room_list[0].pk}",
    )
    attr_value_2 = AttributeValue.objects.create(
        attribute=room_type_room_reference_attribute,
        name=room_list[1].name,
        slug=f"{variant.pk}_{room_list[1].pk}",
    )
    attr_value_3 = AttributeValue.objects.create(
        attribute=room_type_room_reference_attribute,
        name=room_list[2].name,
        slug=f"{variant.pk}_{room_list[2].pk}",
    )

    attr_values = [attr_value_2, attr_value_1, attr_value_3]
    associate_attribute_values_to_instance(
        variant, room_type_room_reference_attribute, *attr_values
    )

    variant_id = graphene.Node.to_global_id("RoomVariant", variant.id)
    variables = {"id": variant_id}
    staff_api_client.user.user_permissions.add(permission_manage_rooms)

    # when
    response = staff_api_client.post_graphql(VARIANT_QUERY, variables)

    # then
    content = get_graphql_content(response)
    data = content["data"]["roomVariant"]
    assert len(data["attributes"]) == 1
    values = data["attributes"][0]["values"]
    assert len(values) == 3
    assert [value["id"] for value in values] == [
        graphene.Node.to_global_id("AttributeValue", val.pk) for val in attr_values
    ]
