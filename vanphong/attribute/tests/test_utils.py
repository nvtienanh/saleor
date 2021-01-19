import pytest

from ..models import RoomType
from ..utils import associate_attribute_values_to_instance


def test_associate_attribute_to_non_room_instance(color_attribute):
    instance = RoomType()
    attribute = color_attribute
    value = color_attribute.values.first()

    with pytest.raises(AssertionError) as exc:
        associate_attribute_values_to_instance(instance, attribute, value)  # noqa

    assert exc.value.args == ("RoomType is unsupported",)


def test_associate_attribute_to_room_instance_from_different_attribute(
    room, color_attribute, size_attribute
):
    """Ensure an assertion error is raised when one tries to associate attribute values
    to an object that don't belong to the supplied attribute.
    """
    instance = room
    attribute = color_attribute
    value = size_attribute.values.first()

    with pytest.raises(AssertionError) as exc:
        associate_attribute_values_to_instance(instance, attribute, value)

    assert exc.value.args == ("Some values are not from the provided attribute.",)


def test_associate_attribute_to_room_instance_without_values(room):
    """Ensure clearing the values from a room is properly working."""
    old_assignment = room.attributes.first()
    assert old_assignment is not None, "The room doesn't have attribute-values"
    assert old_assignment.values.count() == 1

    attribute = old_assignment.attribute

    # Clear the values
    new_assignment = associate_attribute_values_to_instance(room, attribute)

    # Ensure the values were cleared and no new assignment entry was created
    assert new_assignment.pk == old_assignment.pk
    assert new_assignment.values.count() == 0
