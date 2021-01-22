from django.db import models

from ...core.models import SortableModel
from ...room.models import RoomType, RoomVariant
from .base import AssociatedAttributeQuerySet, BaseAssignedAttribute


class AssignedVariantAttributeValue(SortableModel):
    value = models.ForeignKey(
        "AttributeValue",
        on_delete=models.CASCADE,
        related_name="variantvalueassignment",
    )
    assignment = models.ForeignKey(
        "AssignedVariantAttribute",
        on_delete=models.CASCADE,
        related_name="variantvalueassignment",
    )

    class Meta:
        unique_together = (("value", "assignment"),)
        ordering = ("sort_order", "pk")

    def get_ordering_queryset(self):
        return self.assignment.variantvalueassignment.all()


class AssignedVariantAttribute(BaseAssignedAttribute):
    """Associate a room type attribute and selected values to a given variant."""

    variant = models.ForeignKey(
        RoomVariant, related_name="attributes", on_delete=models.CASCADE
    )
    assignment = models.ForeignKey(
        "AttributeVariant", on_delete=models.CASCADE, related_name="variantassignments"
    )
    values = models.ManyToManyField(
        "AttributeValue",
        blank=True,
        related_name="variantassignments",
        through=AssignedVariantAttributeValue,
    )

    class Meta:
        unique_together = (("variant", "assignment"),)


class AttributeVariant(SortableModel):
    attribute = models.ForeignKey(
        "Attribute", related_name="attributevariant", on_delete=models.CASCADE
    )
    room_type = models.ForeignKey(
        RoomType, related_name="attributevariant", on_delete=models.CASCADE
    )
    assigned_variants = models.ManyToManyField(
        RoomVariant,
        blank=True,
        through=AssignedVariantAttribute,
        through_fields=("assignment", "variant"),
        related_name="attributesrelated",
    )

    objects = AssociatedAttributeQuerySet.as_manager()

    class Meta:
        unique_together = (("attribute", "room_type"),)
        ordering = ("sort_order", "pk")

    def get_ordering_queryset(self):
        return self.room_type.attributevariant.all()
