from collections import defaultdict

from promise import Promise

from ....attribute.models import (
    AssignedRoomAttribute,
    AssignedRoomAttributeValue,
    AssignedVariantAttribute,
    AssignedVariantAttributeValue,
    AttributeRoom,
    AttributeVariant,
)
from ....core.permissions import RoomPermissions
from ...attribute.dataloaders import AttributesByAttributeId, AttributeValueByIdLoader
from ...core.dataloaders import DataLoader
from ...utils import get_user_or_app_from_context
from .rooms import RoomByIdLoader, RoomVariantByIdLoader


class BaseRoomAttributesByRoomTypeIdLoader(DataLoader):
    """Loads room attributes by room type ID."""

    context_key = "room_attributes_by_roomtype"
    model_name = None

    def batch_load(self, keys):
        if not self.model_name:
            raise ValueError("Provide a model_name for this dataloader.")

        requestor = get_user_or_app_from_context(self.context)
        if requestor.is_active and requestor.has_perm(
            RoomPermissions.MANAGE_ROOMS
        ):
            qs = self.model_name.objects.all()
        else:
            qs = self.model_name.objects.filter(attribute__visible_in_storefront=True)
        room_type_attribute_pairs = qs.filter(room_type_id__in=keys).values_list(
            "room_type_id", "attribute_id"
        )

        room_type_to_attributes_map = defaultdict(list)
        for room_type_id, attr_id in room_type_attribute_pairs:
            room_type_to_attributes_map[room_type_id].append(attr_id)

        def map_attributes(attributes):
            attributes_map = {attr.id: attr for attr in attributes}
            return [
                [
                    attributes_map[attr_id]
                    for attr_id in room_type_to_attributes_map[room_type_id]
                ]
                for room_type_id in keys
            ]

        return (
            AttributesByAttributeId(self.context)
            .load_many(set(attr_id for _, attr_id in room_type_attribute_pairs))
            .then(map_attributes)
        )


class RoomAttributesByRoomTypeIdLoader(
    BaseRoomAttributesByRoomTypeIdLoader
):
    """Loads room attributes by room type ID."""

    context_key = "room_attributes_by_roomtype"
    model_name = AttributeRoom


class VariantAttributesByRoomTypeIdLoader(
    BaseRoomAttributesByRoomTypeIdLoader
):
    """Loads variant attributes by room type ID."""

    context_key = "variant_attributes_by_roomtype"
    model_name = AttributeVariant


class AttributeRoomsByRoomTypeIdLoader(DataLoader):
    """Loads AttributeRoom objects by room type ID."""

    context_key = "attributerooms_by_roomtype"

    def batch_load(self, keys):
        requestor = get_user_or_app_from_context(self.context)
        if requestor.is_active and requestor.has_perm(
            RoomPermissions.MANAGE_ROOMS
        ):
            qs = AttributeRoom.objects.all()
        else:
            qs = AttributeRoom.objects.filter(attribute__visible_in_storefront=True)
        attribute_rooms = qs.filter(room_type_id__in=keys)
        roomtype_to_attributerooms = defaultdict(list)
        for attribute_room in attribute_rooms:
            roomtype_to_attributerooms[attribute_room.room_type_id].append(
                attribute_room
            )
        return [roomtype_to_attributerooms[key] for key in keys]


class AttributeVariantsByRoomTypeIdLoader(DataLoader):
    context_key = "attributevariants_by_roomtype"

    def batch_load(self, keys):
        requestor = get_user_or_app_from_context(self.context)
        if requestor.is_active and requestor.has_perm(
            RoomPermissions.MANAGE_ROOMS
        ):
            qs = AttributeVariant.objects.all()
        else:
            qs = AttributeVariant.objects.filter(attribute__visible_in_storefront=True)
        attribute_variants = qs.filter(room_type_id__in=keys)
        roomtype_to_attributevariants = defaultdict(list)
        for attribute_variant in attribute_variants:
            roomtype_to_attributevariants[attribute_variant.room_type_id].append(
                attribute_variant
            )
        return [roomtype_to_attributevariants[key] for key in keys]


class AssignedRoomAttributesByRoomIdLoader(DataLoader):
    context_key = "assignedroomattributes_by_room"

    def batch_load(self, keys):
        requestor = get_user_or_app_from_context(self.context)
        if requestor.is_active and requestor.has_perm(
            RoomPermissions.MANAGE_ROOMS
        ):
            qs = AssignedRoomAttribute.objects.all()
        else:
            qs = AssignedRoomAttribute.objects.filter(
                assignment__attribute__visible_in_storefront=True
            )
        assigned_room_attributes = qs.filter(room_id__in=keys)
        room_to_assignedroomattributes = defaultdict(list)
        for assigned_room_attribute in assigned_room_attributes:
            room_to_assignedroomattributes[
                assigned_room_attribute.room_id
            ].append(assigned_room_attribute)
        return [room_to_assignedroomattributes[room_id] for room_id in keys]


class AssignedVariantAttributesByRoomVariantId(DataLoader):
    context_key = "assignedvariantattributes_by_roomvariant"

    def batch_load(self, keys):
        requestor = get_user_or_app_from_context(self.context)
        if requestor.is_active and requestor.has_perm(
            RoomPermissions.MANAGE_ROOMS
        ):
            qs = AssignedVariantAttribute.objects.all()
        else:
            qs = AssignedVariantAttribute.objects.filter(
                assignment__attribute__visible_in_storefront=True
            )
        assigned_variant_attributes = qs.filter(variant_id__in=keys).select_related(
            "assignment__attribute"
        )
        variant_attributes = defaultdict(list)
        for assigned_variant_attribute in assigned_variant_attributes:
            variant_attributes[assigned_variant_attribute.variant_id].append(
                assigned_variant_attribute
            )
        return [variant_attributes[variant_id] for variant_id in keys]


class AttributeValuesByAssignedRoomAttributeIdLoader(DataLoader):
    context_key = "attributevalues_by_assignedroomattribute"

    def batch_load(self, keys):
        attribute_values = AssignedRoomAttributeValue.objects.filter(
            assignment_id__in=keys
        )
        value_ids = [a.value_id for a in attribute_values]

        def map_assignment_to_values(values):
            value_map = dict(zip(value_ids, values))
            assigned_room_map = defaultdict(list)
            for attribute_value in attribute_values:
                assigned_room_map[attribute_value.assignment_id].append(
                    value_map.get(attribute_value.value_id)
                )
            return [assigned_room_map[key] for key in keys]

        return (
            AttributeValueByIdLoader(self.context)
            .load_many(value_ids)
            .then(map_assignment_to_values)
        )


class AttributeValuesByAssignedVariantAttributeIdLoader(DataLoader):
    context_key = "attributevalues_by_assignedvariantattribute"

    def batch_load(self, keys):
        attribute_values = AssignedVariantAttributeValue.objects.filter(
            assignment_id__in=keys
        )
        value_ids = [a.value_id for a in attribute_values]

        def map_assignment_to_values(values):
            value_map = dict(zip(value_ids, values))
            assigned_variant_map = defaultdict(list)
            for attribute_value in attribute_values:
                assigned_variant_map[attribute_value.assignment_id].append(
                    value_map.get(attribute_value.value_id)
                )
            return [assigned_variant_map[key] for key in keys]

        return (
            AttributeValueByIdLoader(self.context)
            .load_many(value_ids)
            .then(map_assignment_to_values)
        )


class SelectedAttributesByRoomIdLoader(DataLoader):
    context_key = "selectedattributes_by_room"

    def batch_load(self, keys):
        def with_rooms_and_assigned_attributes(result):
            rooms, room_attributes = result
            assigned_room_attribute_ids = [
                a.id for attrs in room_attributes for a in attrs
            ]
            room_type_ids = list({p.room_type_id for p in rooms})
            room_attributes = dict(zip(keys, room_attributes))

            def with_attributerooms_and_values(result):
                attribute_rooms, attribute_values = result
                attribute_ids = list(
                    {ap.attribute_id for aps in attribute_rooms for ap in aps}
                )
                attribute_rooms = dict(zip(room_type_ids, attribute_rooms))
                attribute_values = dict(
                    zip(assigned_room_attribute_ids, attribute_values)
                )

                def with_attributes(attributes):
                    id_to_attribute = dict(zip(attribute_ids, attributes))
                    selected_attributes_map = defaultdict(list)
                    for key, room in zip(keys, rooms):
                        assigned_roomtype_attributes = attribute_rooms[
                            room.room_type_id
                        ]
                        assigned_room_attributes = room_attributes[key]
                        for (
                            assigned_roomtype_attribute
                        ) in assigned_roomtype_attributes:
                            room_assignment = next(
                                (
                                    apa
                                    for apa in assigned_room_attributes
                                    if apa.assignment_id
                                    == assigned_roomtype_attribute.id
                                ),
                                None,
                            )
                            attribute = id_to_attribute[
                                assigned_roomtype_attribute.attribute_id
                            ]
                            if room_assignment:
                                values = attribute_values[room_assignment.id]
                            else:
                                values = []
                            selected_attributes_map[key].append(
                                {"values": values, "attribute": attribute}
                            )
                    return [selected_attributes_map[key] for key in keys]

                return (
                    AttributesByAttributeId(self.context)
                    .load_many(attribute_ids)
                    .then(with_attributes)
                )

            attribute_rooms = AttributeRoomsByRoomTypeIdLoader(
                self.context
            ).load_many(room_type_ids)
            attribute_values = AttributeValuesByAssignedRoomAttributeIdLoader(
                self.context
            ).load_many(assigned_room_attribute_ids)
            return Promise.all([attribute_rooms, attribute_values]).then(
                with_attributerooms_and_values
            )

        rooms = RoomByIdLoader(self.context).load_many(keys)
        assigned_attributes = AssignedRoomAttributesByRoomIdLoader(
            self.context
        ).load_many(keys)

        return Promise.all([rooms, assigned_attributes]).then(
            with_rooms_and_assigned_attributes
        )


class SelectedAttributesByRoomVariantIdLoader(DataLoader):
    context_key = "selectedattributes_by_roomvariant"

    def batch_load(self, keys):
        def with_variants_and_assigned_attributed(results):
            room_variants, variant_attributes = results
            room_ids = list({v.room_id for v in room_variants})
            assigned_variant_attribute_ids = [
                a.id for attrs in variant_attributes for a in attrs
            ]
            variant_attributes = dict(zip(keys, variant_attributes))

            def with_rooms_and_attribute_values(results):
                rooms, attribute_values = results
                room_type_ids = list({p.room_type_id for p in rooms})
                rooms = dict(zip(room_ids, rooms))
                attribute_values = dict(
                    zip(assigned_variant_attribute_ids, attribute_values)
                )

                def with_attribute_rooms(attribute_rooms):
                    attribute_ids = list(
                        {ap.attribute_id for aps in attribute_rooms for ap in aps}
                    )
                    attribute_rooms = dict(zip(room_type_ids, attribute_rooms))

                    def with_attributes(attributes):
                        id_to_attribute = dict(zip(attribute_ids, attributes))
                        selected_attributes_map = defaultdict(list)
                        for key, room_variant in zip(keys, room_variants):
                            room = rooms[room_variant.room_id]
                            assigned_roomtype_attributes = attribute_rooms[
                                room.room_type_id
                            ]
                            assigned_variant_attributes = variant_attributes[key]
                            for (
                                assigned_roomtype_attribute
                            ) in assigned_roomtype_attributes:
                                variant_assignment = next(
                                    (
                                        apa
                                        for apa in assigned_variant_attributes
                                        if apa.assignment_id
                                        == assigned_roomtype_attribute.id
                                    ),
                                    None,
                                )
                                attribute = id_to_attribute[
                                    assigned_roomtype_attribute.attribute_id
                                ]
                                if variant_assignment:
                                    values = attribute_values[variant_assignment.id]
                                else:
                                    values = []
                                selected_attributes_map[key].append(
                                    {"values": values, "attribute": attribute}
                                )
                        return [selected_attributes_map[key] for key in keys]

                    return (
                        AttributesByAttributeId(self.context)
                        .load_many(attribute_ids)
                        .then(with_attributes)
                    )

                return (
                    AttributeVariantsByRoomTypeIdLoader(self.context)
                    .load_many(room_type_ids)
                    .then(with_attribute_rooms)
                )

            rooms = RoomByIdLoader(self.context).load_many(room_ids)
            attribute_values = AttributeValuesByAssignedVariantAttributeIdLoader(
                self.context
            ).load_many(assigned_variant_attribute_ids)

            return Promise.all([rooms, attribute_values]).then(
                with_rooms_and_attribute_values
            )

        room_variants = RoomVariantByIdLoader(self.context).load_many(keys)
        assigned_attributes = AssignedVariantAttributesByRoomVariantId(
            self.context
        ).load_many(keys)

        return Promise.all([room_variants, assigned_attributes]).then(
            with_variants_and_assigned_attributed
        )
