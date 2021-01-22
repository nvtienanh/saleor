from typing import TYPE_CHECKING, Iterable, Set, Union

from ..page.models import Page
from ..room.models import Room, RoomVariant
from .models import (
    AssignedPageAttribute,
    AssignedPageAttributeValue,
    AssignedRoomAttribute,
    AssignedRoomAttributeValue,
    AssignedVariantAttribute,
    AssignedVariantAttributeValue,
    Attribute,
    AttributeValue,
)

AttributeAssignmentType = Union[
    AssignedRoomAttribute, AssignedVariantAttribute, AssignedPageAttribute
]
T_INSTANCE = Union[Room, RoomVariant, Page]


if TYPE_CHECKING:
    from .models import AttributePage, AttributeRoom, AttributeVariant


def associate_attribute_values_to_instance(
    instance: T_INSTANCE,
    attribute: Attribute,
    *values: AttributeValue,
) -> AttributeAssignmentType:
    """Assign given attribute values to a room or variant.

    Note: be award this function invokes the ``set`` method on the instance's
    attribute association. Meaning any values already assigned or concurrently
    assigned will be overridden by this call.
    """
    values_ids = {value.pk for value in values}

    # Ensure the values are actually form the given attribute
    validate_attribute_owns_values(attribute, values_ids)

    # Associate the attribute and the passed values
    assignment = _associate_attribute_to_instance(instance, attribute.pk)
    assignment.values.set(values)
    sort_assigned_attribute_values(instance, assignment, values)

    return assignment


def validate_attribute_owns_values(attribute: Attribute, value_ids: Set[int]) -> None:
    """Check given value IDs are belonging to the given attribute.

    :raise: AssertionError
    """
    attribute_actual_value_ids = set(attribute.values.values_list("pk", flat=True))
    found_associated_ids = attribute_actual_value_ids & value_ids
    if found_associated_ids != value_ids:
        raise AssertionError("Some values are not from the provided attribute.")


def _associate_attribute_to_instance(
    instance: T_INSTANCE, attribute_pk: int
) -> AttributeAssignmentType:
    """Associate a given attribute to an instance."""
    assignment: AttributeAssignmentType
    if isinstance(instance, Room):
        attribute_rel: Union[
            "AttributeRoom", "AttributeVariant", "AttributePage"
        ] = instance.room_type.attributeroom.get(attribute_id=attribute_pk)

        assignment, _ = AssignedRoomAttribute.objects.get_or_create(
            room=instance, assignment=attribute_rel
        )
    elif isinstance(instance, RoomVariant):
        attribute_rel = instance.room.room_type.attributevariant.get(
            attribute_id=attribute_pk
        )

        assignment, _ = AssignedVariantAttribute.objects.get_or_create(
            variant=instance, assignment=attribute_rel
        )
    elif isinstance(instance, Page):
        attribute_rel = instance.page_type.attributepage.get(attribute_id=attribute_pk)
        assignment, _ = AssignedPageAttribute.objects.get_or_create(
            page=instance, assignment=attribute_rel
        )
    else:
        raise AssertionError(f"{instance.__class__.__name__} is unsupported")

    return assignment


def sort_assigned_attribute_values(
    instance: T_INSTANCE,
    assignment: AttributeAssignmentType,
    values: Iterable[AttributeValue],
) -> None:
    """Sort assigned attribute values based on values list order."""

    instance_to_value_assignment_mapping = {
        "Room": ("roomvalueassignment", AssignedRoomAttributeValue),
        "RoomVariant": ("variantvalueassignment", AssignedVariantAttributeValue),
        "Page": ("pagevalueassignment", AssignedPageAttributeValue),
    }
    assignment_lookup, assignment_model = instance_to_value_assignment_mapping[
        instance.__class__.__name__
    ]
    values_pks = [value.pk for value in values]

    values_assignment = list(
        getattr(assignment, assignment_lookup).select_related("value")
    )
    values_assignment.sort(key=lambda e: values_pks.index(e.value.pk))
    for index, value_assignment in enumerate(values_assignment):
        value_assignment.sort_order = index

    assignment_model.objects.bulk_update(values_assignment, ["sort_order"])
