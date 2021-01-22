from django.db import models

from ...core.models import SortableModel
from ...room.models import Room, RoomType
from .base import AssociatedAttributeQuerySet, BaseAssignedAttribute


class AssignedRoomAttributeValue(SortableModel):
    value = models.ForeignKey(
        "AttributeValue",
        on_delete=models.CASCADE,
        related_name="roomvalueassignment",
    )
    assignment = models.ForeignKey(
        "AssignedRoomAttribute",
        on_delete=models.CASCADE,
        related_name="roomvalueassignment",
    )

    class Meta:
        unique_together = (("value", "assignment"),)
        ordering = ("sort_order", "pk")

    def get_ordering_queryset(self):
        return self.assignment.roomvalueassignment.all()


class AssignedRoomAttribute(BaseAssignedAttribute):
    """Associate a room type attribute and selected values to a given room."""

    room = models.ForeignKey(
        Room, related_name="attributes", on_delete=models.CASCADE
    )
    assignment = models.ForeignKey(
        "AttributeRoom", on_delete=models.CASCADE, related_name="roomassignments"
    )
    values = models.ManyToManyField(
        "AttributeValue",
        blank=True,
        related_name="roomassignments",
        through=AssignedRoomAttributeValue,
    )

    class Meta:
        unique_together = (("room", "assignment"),)


class AttributeRoom(SortableModel):
    attribute = models.ForeignKey(
        "Attribute", related_name="attributeroom", on_delete=models.CASCADE
    )
    room_type = models.ForeignKey(
        RoomType, related_name="attributeroom", on_delete=models.CASCADE
    )
    assigned_rooms = models.ManyToManyField(
        Room,
        blank=True,
        through=AssignedRoomAttribute,
        through_fields=("assignment", "room"),
        related_name="attributesrelated",
    )

    objects = AssociatedAttributeQuerySet.as_manager()

    class Meta:
        unique_together = (("attribute", "room_type"),)
        ordering = ("sort_order", "pk")

    def get_ordering_queryset(self):
        return self.room_type.attributeroom.all()
