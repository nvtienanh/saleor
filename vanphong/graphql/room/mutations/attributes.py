from collections import defaultdict
from typing import List

import graphene
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Q

from ....attribute import AttributeType
from ....attribute import models as attribute_models
from ....core.permissions import RoomPermissions, RoomTypePermissions
from ....room import models
from ....room.error_codes import RoomErrorCode
from ...attribute.mutations import (
    BaseReorderAttributesMutation,
    BaseReorderAttributeValuesMutation,
)
from ...attribute.types import Attribute
from ...channel import ChannelContext
from ...core.inputs import ReorderInput
from ...core.mutations import BaseMutation
from ...core.types.common import RoomError
from ...core.utils import from_global_id_strict_type
from ...core.utils.reordering import perform_reordering
from ...room.types import Room, RoomType, RoomVariant
from ..enums import RoomAttributeType


class RoomAttributeAssignInput(graphene.InputObjectType):
    id = graphene.ID(required=True, description="The ID of the attribute to assign.")
    type = RoomAttributeType(
        required=True, description="The attribute type to be assigned as."
    )


class RoomAttributeAssign(BaseMutation):
    room_type = graphene.Field(RoomType, description="The updated room type.")

    class Arguments:
        room_type_id = graphene.ID(
            required=True,
            description="ID of the room type to assign the attributes into.",
        )
        operations = graphene.List(
            RoomAttributeAssignInput,
            required=True,
            description="The operations to perform.",
        )

    class Meta:
        description = "Assign attributes to a given room type."
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def check_permissions(cls, context):
        return context.user.has_perm(
            RoomTypePermissions.MANAGE_ROOM_TYPES_AND_ATTRIBUTES
        )

    @classmethod
    def get_operations(cls, info, operations: List[RoomAttributeAssignInput]):
        """Resolve all passed global ids into integer PKs of the Attribute type."""
        room_attrs_pks = []
        variant_attrs_pks = []

        for operation in operations:
            pk = from_global_id_strict_type(
                operation.id, only_type=Attribute, field="operations"
            )
            if operation.type == RoomAttributeType.ROOM:
                room_attrs_pks.append(pk)
            else:
                variant_attrs_pks.append(pk)

        return room_attrs_pks, variant_attrs_pks

    @classmethod
    def check_attributes_types(cls, errors, room_attrs_pks, variant_attrs_pks):
        """Ensure the attributes are room attributes."""

        not_valid_attributes = attribute_models.Attribute.objects.filter(
            Q(pk__in=room_attrs_pks) | Q(pk__in=variant_attrs_pks)
        ).exclude(type=AttributeType.ROOM_TYPE)

        if not_valid_attributes:
            not_valid_attr_ids = [
                graphene.Node.to_global_id("Attribute", attr.pk)
                for attr in not_valid_attributes
            ]
            error = ValidationError(
                "Only room attributes can be assigned.",
                code=RoomErrorCode.INVALID.value,
                params={"attributes": not_valid_attr_ids},
            )
            errors["operations"].append(error)

    @classmethod
    def check_operations_not_assigned_already(
        cls, errors, room_type, room_attrs_pks, variant_attrs_pks
    ):
        qs = (
            attribute_models.Attribute.objects.get_assigned_room_type_attributes(
                room_type.pk
            )
            .values_list("pk", "name", "slug")
            .filter(Q(pk__in=room_attrs_pks) | Q(pk__in=variant_attrs_pks))
        )

        invalid_attributes = list(qs)
        if invalid_attributes:
            msg = ", ".join(
                [f"{name} ({slug})" for _, name, slug in invalid_attributes]
            )
            invalid_attr_ids = [
                graphene.Node.to_global_id("Attribute", attr[0])
                for attr in invalid_attributes
            ]
            error = ValidationError(
                (f"{msg} have already been assigned to this room type."),
                code=RoomErrorCode.ATTRIBUTE_ALREADY_ASSIGNED,
                params={"attributes": invalid_attr_ids},
            )
            errors["operations"].append(error)

    @classmethod
    def check_room_operations_are_assignable(cls, errors, room_attrs_pks):
        restricted_attributes = attribute_models.Attribute.objects.filter(
            pk__in=room_attrs_pks, is_variant_only=True
        )

        if restricted_attributes:
            restricted_attr_ids = [
                graphene.Node.to_global_id("Attribute", attr.pk)
                for attr in restricted_attributes
            ]
            error = ValidationError(
                "Cannot assign variant only attributes.",
                code=RoomErrorCode.ATTRIBUTE_CANNOT_BE_ASSIGNED,
                params={"attributes": restricted_attr_ids},
            )
            errors["operations"].append(error)

    @classmethod
    def clean_operations(cls, room_type, room_attrs_pks, variant_attrs_pks):
        """Ensure the attributes are not already assigned to the room type."""
        errors = defaultdict(list)

        attrs_pk = room_attrs_pks + variant_attrs_pks
        attributes = attribute_models.Attribute.objects.filter(
            id__in=attrs_pk
        ).values_list("pk", flat=True)
        if len(attrs_pk) != len(attributes):
            invalid_attrs = set(attrs_pk) - set(attributes)
            invalid_attrs = [
                graphene.Node.to_global_id("Attribute", pk) for pk in invalid_attrs
            ]
            error = ValidationError(
                "Attribute doesn't exist.",
                code=RoomErrorCode.NOT_FOUND,
                params={"attributes": list(invalid_attrs)},
            )
            errors["operations"].append(error)

        cls.check_attributes_types(errors, room_attrs_pks, variant_attrs_pks)
        cls.check_room_operations_are_assignable(errors, room_attrs_pks)
        cls.check_operations_not_assigned_already(
            errors, room_type, room_attrs_pks, variant_attrs_pks
        )

        if errors:
            raise ValidationError(errors)

    @classmethod
    def save_field_values(cls, room_type, model_name, pks):
        """Add in bulk the PKs to assign to a given room type."""
        model = getattr(attribute_models, model_name)
        for pk in pks:
            model.objects.create(room_type=room_type, attribute_id=pk)

    @classmethod
    @transaction.atomic()
    def perform_mutation(cls, _root, info, **data):
        room_type_id: str = data["room_type_id"]
        operations: List[RoomAttributeAssignInput] = data["operations"]
        # Retrieve the requested room type
        room_type: models.RoomType = graphene.Node.get_node_from_global_id(
            info, room_type_id, only_type=RoomType
        )

        # Resolve all the passed IDs to ints
        room_attrs_pks, variant_attrs_pks = cls.get_operations(info, operations)

        if variant_attrs_pks and not room_type.has_variants:
            raise ValidationError(
                {
                    "operations": ValidationError(
                        "Variants are disabled in this room type.",
                        code=RoomErrorCode.ATTRIBUTE_VARIANTS_DISABLED.value,
                    )
                }
            )

        # Ensure the attribute are assignable
        cls.clean_operations(room_type, room_attrs_pks, variant_attrs_pks)

        # Commit
        cls.save_field_values(room_type, "AttributeRoom", room_attrs_pks)
        cls.save_field_values(room_type, "AttributeVariant", variant_attrs_pks)

        return cls(room_type=room_type)


class RoomAttributeUnassign(BaseMutation):
    room_type = graphene.Field(RoomType, description="The updated room type.")

    class Arguments:
        room_type_id = graphene.ID(
            required=True,
            description=(
                "ID of the room type from which the attributes should be unassigned."
            ),
        )
        attribute_ids = graphene.List(
            graphene.ID,
            required=True,
            description="The IDs of the attributes to unassign.",
        )

    class Meta:
        description = "Un-assign attributes from a given room type."
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def check_permissions(cls, context):
        return context.user.has_perm(
            RoomTypePermissions.MANAGE_ROOM_TYPES_AND_ATTRIBUTES
        )

    @classmethod
    def save_field_values(cls, room_type, field, pks):
        """Add in bulk the PKs to assign to a given room type."""
        getattr(room_type, field).remove(*pks)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        room_type_id: str = data["room_type_id"]
        attribute_ids: List[str] = data["attribute_ids"]
        # Retrieve the requested room type
        room_type = graphene.Node.get_node_from_global_id(
            info, room_type_id, only_type=RoomType
        )  # type: models.RoomType

        # Resolve all the passed IDs to ints
        attribute_pks = [
            from_global_id_strict_type(
                attribute_id, only_type=Attribute, field="attribute_id"
            )
            for attribute_id in attribute_ids
        ]

        # Commit
        cls.save_field_values(room_type, "room_attributes", attribute_pks)
        cls.save_field_values(room_type, "variant_attributes", attribute_pks)

        return cls(room_type=room_type)


class RoomTypeReorderAttributes(BaseReorderAttributesMutation):
    room_type = graphene.Field(
        RoomType, description="Room type from which attributes are reordered."
    )

    class Meta:
        description = "Reorder the attributes of a room type."
        permissions = (RoomTypePermissions.MANAGE_ROOM_TYPES_AND_ATTRIBUTES,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    class Arguments:
        room_type_id = graphene.Argument(
            graphene.ID, required=True, description="ID of a room type."
        )
        type = RoomAttributeType(
            required=True, description="The attribute type to reorder."
        )
        moves = graphene.List(
            ReorderInput,
            required=True,
            description="The list of attribute reordering operations.",
        )

    @classmethod
    def perform_mutation(cls, _root, info, room_type_id, type, moves):
        pk = from_global_id_strict_type(
            room_type_id, only_type=RoomType, field="room_type_id"
        )

        if type == RoomAttributeType.ROOM:
            m2m_field = "attributeroom"
        else:
            m2m_field = "attributevariant"

        try:
            room_type = models.RoomType.objects.prefetch_related(m2m_field).get(
                pk=pk
            )
        except ObjectDoesNotExist:
            raise ValidationError(
                {
                    "room_type_id": ValidationError(
                        (f"Couldn't resolve to a room type: {room_type_id}"),
                        code=RoomErrorCode.NOT_FOUND,
                    )
                }
            )

        attributes_m2m = getattr(room_type, m2m_field)

        try:
            operations = cls.prepare_operations(moves, attributes_m2m)
        except ValidationError as error:
            error.code = RoomErrorCode.NOT_FOUND.value
            raise ValidationError({"moves": error})

        with transaction.atomic():
            perform_reordering(attributes_m2m, operations)

        return RoomTypeReorderAttributes(room_type=room_type)


class RoomReorderAttributeValues(BaseReorderAttributeValuesMutation):
    room = graphene.Field(
        Room, description="Room from which attribute values are reordered."
    )

    class Meta:
        description = "Reorder room attribute values."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    class Arguments:
        room_id = graphene.Argument(
            graphene.ID, required=True, description="ID of a room."
        )
        attribute_id = graphene.Argument(
            graphene.ID, required=True, description="ID of an attribute."
        )
        moves = graphene.List(
            ReorderInput,
            required=True,
            description="The list of reordering operations for given attribute values.",
        )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        room_id = data["room_id"]
        room = cls.perform(
            room_id, "room", data, "roomvalueassignment", RoomErrorCode
        )

        return RoomReorderAttributeValues(
            room=ChannelContext(node=room, channel_slug=None)
        )

    @staticmethod
    def get_instance(instance_id: str):
        pk = from_global_id_strict_type(
            instance_id, only_type=Room, field="room_id"
        )

        try:
            room = models.Room.objects.prefetch_related("attributes").get(pk=pk)
        except ObjectDoesNotExist:
            raise ValidationError(
                {
                    "room_id": ValidationError(
                        (f"Couldn't resolve to a room: {instance_id}"),
                        code=RoomErrorCode.NOT_FOUND.value,
                    )
                }
            )
        return room


class RoomVariantReorderAttributeValues(BaseReorderAttributeValuesMutation):
    room_variant = graphene.Field(
        RoomVariant,
        description="Room variant from which attribute values are reordered.",
    )

    class Meta:
        description = "Reorder room variant attribute values."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    class Arguments:
        variant_id = graphene.Argument(
            graphene.ID, required=True, description="ID of a room variant."
        )
        attribute_id = graphene.Argument(
            graphene.ID, required=True, description="ID of an attribute."
        )
        moves = graphene.List(
            ReorderInput,
            required=True,
            description="The list of reordering operations for given attribute values.",
        )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        variant_id = data["variant_id"]
        variant = cls.perform(
            variant_id, "variant", data, "variantvalueassignment", RoomErrorCode
        )

        return RoomVariantReorderAttributeValues(
            room_variant=ChannelContext(node=variant, channel_slug=None)
        )

    @staticmethod
    def get_instance(instance_id: str):
        pk = from_global_id_strict_type(
            instance_id, only_type=RoomVariant, field="variant_id"
        )

        try:
            variant = models.RoomVariant.objects.prefetch_related("attributes").get(
                pk=pk
            )
        except ObjectDoesNotExist:
            raise ValidationError(
                {
                    "variant_id": ValidationError(
                        (f"Couldn't resolve to a room variant: {instance_id}"),
                        code=RoomErrorCode.NOT_FOUND.value,
                    )
                }
            )
        return variant
