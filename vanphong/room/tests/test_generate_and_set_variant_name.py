from decimal import Decimal
from unittest.mock import MagicMock, Mock

import pytest

from ...attribute import AttributeInputType
from ...attribute.models import AttributeValue
from ...attribute.utils import associate_attribute_values_to_instance
from ...room.models import RoomVariantChannelListing
from ..models import Room, RoomType, RoomVariant
from ..tasks import _update_variants_names
from ..utils.variants import generate_and_set_variant_name


@pytest.fixture()
def variant_with_no_attributes(category, channel_USD):
    """Create a variant having no attributes, the same for the parent room."""
    room_type = RoomType.objects.create(
        name="Test room type", has_variants=True, is_shipping_required=True
    )
    room = Room.objects.create(
        name="Test room",
        room_type=room_type,
        category=category,
    )
    variant = RoomVariant.objects.create(room=room, sku="123")
    RoomVariantChannelListing.objects.create(
        variant=variant,
        channel=channel_USD,
        cost_price_amount=Decimal(1),
        price_amount=Decimal(10),
        currency=channel_USD.currency_code,
    )
    return variant


def test_generate_and_set_variant_name_different_attributes(
    variant_with_no_attributes, color_attribute_without_values, size_attribute
):
    """Test the name generation from a given variant containing multiple attributes and
    different input types (dropdown and multiselect).
    """

    variant = variant_with_no_attributes
    color_attribute = color_attribute_without_values

    # Assign the attributes to the room type
    variant.room.room_type.variant_attributes.set(
        (color_attribute, size_attribute)
    )

    # Set the color attribute to a multi-value attribute
    color_attribute.input_type = AttributeInputType.MULTISELECT
    color_attribute.save(update_fields=["input_type"])

    # Create colors
    colors = AttributeValue.objects.bulk_create(
        [
            AttributeValue(attribute=color_attribute, name="Yellow", slug="yellow"),
            AttributeValue(attribute=color_attribute, name="Blue", slug="blue"),
            AttributeValue(attribute=color_attribute, name="Red", slug="red"),
        ]
    )

    # Retrieve the size attribute value "Big"
    size = size_attribute.values.get(slug="big")

    # Associate the colors and size to variant attributes
    associate_attribute_values_to_instance(variant, color_attribute, *tuple(colors))
    associate_attribute_values_to_instance(variant, size_attribute, size)

    # Generate the variant name from the attributes
    generate_and_set_variant_name(variant, variant.sku)
    variant.refresh_from_db()
    assert variant.name == "Big"


def test_generate_and_set_variant_name_only_variant_selection_attributes(
    variant_with_no_attributes, color_attribute_without_values, size_attribute
):
    """Test the name generation for a given variant containing multiple attributes
    with input types allowed in variant selection.
    """

    variant = variant_with_no_attributes
    color_attribute = color_attribute_without_values

    # Assign the attributes to the room type
    variant.room.room_type.variant_attributes.set(
        (color_attribute, size_attribute)
    )

    # Create values
    colors = AttributeValue.objects.bulk_create(
        [
            AttributeValue(
                attribute=color_attribute, name="Yellow", slug="yellow", sort_order=1
            ),
            AttributeValue(
                attribute=color_attribute, name="Blue", slug="blue", sort_order=2
            ),
            AttributeValue(
                attribute=color_attribute, name="Red", slug="red", sort_order=3
            ),
        ]
    )

    # Retrieve the size attribute value "Big"
    size = size_attribute.values.get(slug="big")
    size.sort_order = 4
    size.save(update_fields=["sort_order"])

    # Associate the colors and size to variant attributes
    associate_attribute_values_to_instance(variant, color_attribute, *tuple(colors))
    associate_attribute_values_to_instance(variant, size_attribute, size)

    # Generate the variant name from the attributes
    generate_and_set_variant_name(variant, variant.sku)
    variant.refresh_from_db()
    assert variant.name == "Big / Yellow, Blue, Red"


def test_generate_and_set_variant_name_only_not_variant_selection_attributes(
    variant_with_no_attributes, color_attribute_without_values, file_attribute
):
    """Test the name generation for a given variant containing multiple attributes
    with input types not allowed in variant selection.
    """

    variant = variant_with_no_attributes
    color_attribute = color_attribute_without_values

    # Assign the attributes to the room type
    variant.room.room_type.variant_attributes.set(
        (color_attribute, file_attribute)
    )

    # Set the color attribute to a multi-value attribute
    color_attribute.input_type = AttributeInputType.MULTISELECT
    color_attribute.save(update_fields=["input_type"])

    # Create values
    values = AttributeValue.objects.bulk_create(
        [
            AttributeValue(attribute=color_attribute, name="Yellow", slug="yellow"),
            AttributeValue(attribute=color_attribute, name="Blue", slug="blue"),
            AttributeValue(
                attribute=file_attribute,
                name="test_file_3.txt",
                slug="test_file3txt",
                file_url="http://mirumee.com/test_media/test_file3.txt",
                content_type="text/plain",
            ),
        ]
    )

    # Associate the colors and size to variant attributes
    associate_attribute_values_to_instance(variant, color_attribute, *values[:2])
    associate_attribute_values_to_instance(variant, file_attribute, values[-1])

    # Generate the variant name from the attributes
    generate_and_set_variant_name(variant, variant.sku)
    variant.refresh_from_db()
    assert variant.name == variant.sku


def test_generate_name_from_values_empty(variant_with_no_attributes):
    """Ensure generate a variant name from a variant without any attributes assigned
    returns an empty string."""
    variant = variant_with_no_attributes
    generate_and_set_variant_name(variant, variant.sku)
    variant.refresh_from_db()
    assert variant.name == variant.sku


def test_room_type_update_changes_variant_name(room):
    new_name = "test_name"
    room_variant = room.variants.first()
    assert not room_variant.name == new_name
    attribute = room.room_type.variant_attributes.first()
    attribute_value = attribute.values.first()
    attribute_value.name = new_name
    attribute_value.save()
    _update_variants_names(room.room_type, [attribute])
    room_variant.refresh_from_db()
    assert room_variant.name == new_name


def test_only_not_variant_selection_attr_left_variant_name_change_to_sku(room):
    new_name = "test_name"
    room_variant = room.variants.first()
    assert not room_variant.name == new_name
    attribute = room.room_type.variant_attributes.first()
    attribute.input_type = AttributeInputType.MULTISELECT
    attribute.save(update_fields=["input_type"])
    _update_variants_names(room.room_type, [attribute])
    room_variant.refresh_from_db()
    assert room_variant.name == room_variant.sku


def test_update_variants_changed_does_nothing_with_no_attributes():
    room_type = MagicMock(spec=RoomType)
    room_type.variant_attributes.all = Mock(return_value=[])
    saved_attributes = []
    # FIXME: This method no longer returns any value
    assert _update_variants_names(room_type, saved_attributes) is None