import datetime
from collections import defaultdict
from typing import List, Tuple

import graphene
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.utils.text import slugify
from graphene.types import InputObjectType

from ....attribute import AttributeInputType, AttributeType
from ....attribute import models as attribute_models
from ....core.exceptions import PermissionDenied
from ....core.permissions import RoomPermissions, RoomTypePermissions
from ....order import OrderStatus
from ....order import models as order_models
from ....room import models
from ....room.error_codes import CollectionErrorCode, RoomErrorCode
from ....room.tasks import (
    update_room_discounted_price_task,
    update_rooms_discounted_prices_of_catalogues_task,
    update_variants_names,
)
from ....room.thumbnails import (
    create_category_background_image_thumbnails,
    create_collection_background_image_thumbnails,
    create_room_thumbnails,
)
from ....room.utils import delete_categories, get_rooms_ids_without_variants
from ....room.utils.variants import generate_and_set_variant_name
from ...attribute.utils import AttributeAssignmentMixin, AttrValuesInput
from ...channel import ChannelContext
from ...core.inputs import ReorderInput
from ...core.mutations import BaseMutation, ModelDeleteMutation, ModelMutation
from ...core.scalars import WeightScalar
from ...core.types import SeoInput, Upload
from ...core.types.common import CollectionError, RoomError
from ...core.utils import (
    clean_seo_fields,
    from_global_id_strict_type,
    get_duplicated_values,
    validate_image_file,
    validate_slug_and_generate_if_needed,
)
from ...core.utils.reordering import perform_reordering
from ...hotel.types import Hotel
from ..types import (
    Category,
    Collection,
    Room,
    RoomImage,
    RoomType,
    RoomVariant,
)
from ..utils import (
    create_stocks,
    get_used_attribute_values_for_variant,
    get_used_variants_attribute_values,
)


class CategoryInput(graphene.InputObjectType):
    description = graphene.String(description="Category description (HTML/text).")
    description_json = graphene.JSONString(description="Category description (JSON).")
    name = graphene.String(description="Category name.")
    slug = graphene.String(description="Category slug.")
    seo = SeoInput(description="Search engine optimization fields.")
    background_image = Upload(description="Background image file.")
    background_image_alt = graphene.String(description="Alt text for an image.")


class CategoryCreate(ModelMutation):
    class Arguments:
        input = CategoryInput(
            required=True, description="Fields required to create a category."
        )
        parent_id = graphene.ID(
            description=(
                "ID of the parent category. If empty, category will be top level "
                "category."
            ),
            name="parent",
        )

    class Meta:
        description = "Creates a new category."
        model = models.Category
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def clean_input(cls, info, instance, data):
        cleaned_input = super().clean_input(info, instance, data)
        try:
            cleaned_input = validate_slug_and_generate_if_needed(
                instance, "name", cleaned_input
            )
        except ValidationError as error:
            error.code = RoomErrorCode.REQUIRED.value
            raise ValidationError({"slug": error})
        parent_id = data["parent_id"]
        if parent_id:
            parent = cls.get_node_or_error(
                info, parent_id, field="parent", only_type=Category
            )
            cleaned_input["parent"] = parent
        if data.get("background_image"):
            image_data = info.context.FILES.get(data["background_image"])
            validate_image_file(image_data, "background_image")
        clean_seo_fields(cleaned_input)
        return cleaned_input

    @classmethod
    def perform_mutation(cls, root, info, **data):
        parent_id = data.pop("parent_id", None)
        data["input"]["parent_id"] = parent_id
        return super().perform_mutation(root, info, **data)

    @classmethod
    def save(cls, info, instance, cleaned_input):
        instance.save()
        if cleaned_input.get("background_image"):
            create_category_background_image_thumbnails.delay(instance.pk)


class CategoryUpdate(CategoryCreate):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a category to update.")
        input = CategoryInput(
            required=True, description="Fields required to update a category."
        )

    class Meta:
        description = "Updates a category."
        model = models.Category
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"


class CategoryDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a category to delete.")

    class Meta:
        description = "Deletes a category."
        model = models.Category
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        if not cls.check_permissions(info.context):
            raise PermissionDenied()
        node_id = data.get("id")
        instance = cls.get_node_or_error(info, node_id, only_type=Category)

        db_id = instance.id

        delete_categories([db_id])

        instance.id = db_id
        return cls.success_response(instance)


class CollectionInput(graphene.InputObjectType):
    is_published = graphene.Boolean(
        description="Informs whether a collection is published."
    )
    name = graphene.String(description="Name of the collection.")
    slug = graphene.String(description="Slug of the collection.")
    description = graphene.String(
        description="Description of the collection (HTML/text)."
    )
    description_json = graphene.JSONString(
        description="Description of the collection (JSON)."
    )
    background_image = Upload(description="Background image file.")
    background_image_alt = graphene.String(description="Alt text for an image.")
    seo = SeoInput(description="Search engine optimization fields.")
    publication_date = graphene.Date(description="Publication date. ISO 8601 standard.")


class CollectionCreateInput(CollectionInput):
    rooms = graphene.List(
        graphene.ID,
        description="List of rooms to be added to the collection.",
        name="rooms",
    )


class CollectionCreate(ModelMutation):
    class Arguments:
        input = CollectionCreateInput(
            required=True, description="Fields required to create a collection."
        )

    class Meta:
        description = "Creates a new collection."
        model = models.Collection
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = CollectionError
        error_type_field = "collection_errors"

    @classmethod
    def clean_input(cls, info, instance, data):
        cleaned_input = super().clean_input(info, instance, data)
        try:
            cleaned_input = validate_slug_and_generate_if_needed(
                instance, "name", cleaned_input
            )
        except ValidationError as error:
            error.code = CollectionErrorCode.REQUIRED.value
            raise ValidationError({"slug": error})
        if data.get("background_image"):
            image_data = info.context.FILES.get(data["background_image"])
            validate_image_file(image_data, "background_image")
        is_published = cleaned_input.get("is_published")
        publication_date = cleaned_input.get("publication_date")
        if is_published and not publication_date:
            cleaned_input["publication_date"] = datetime.date.today()
        clean_seo_fields(cleaned_input)
        return cleaned_input

    @classmethod
    def save(cls, info, instance, cleaned_input):
        instance.save()
        if cleaned_input.get("background_image"):
            create_collection_background_image_thumbnails.delay(instance.pk)

    @classmethod
    def perform_mutation(cls, _root, info, **kwargs):
        result = super().perform_mutation(_root, info, **kwargs)
        return CollectionCreate(
            collection=ChannelContext(node=result.collection, channel_slug=None)
        )


class CollectionUpdate(CollectionCreate):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a collection to update.")
        input = CollectionInput(
            required=True, description="Fields required to update a collection."
        )

    class Meta:
        description = "Updates a collection."
        model = models.Collection
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = CollectionError
        error_type_field = "collection_errors"

    @classmethod
    def save(cls, info, instance, cleaned_input):
        if cleaned_input.get("background_image"):
            create_collection_background_image_thumbnails.delay(instance.pk)
        instance.save()


class CollectionDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a collection to delete.")

    class Meta:
        description = "Deletes a collection."
        model = models.Collection
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = CollectionError
        error_type_field = "collection_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **kwargs):
        result = super().perform_mutation(_root, info, **kwargs)
        return CollectionDelete(
            collection=ChannelContext(node=result.collection, channel_slug=None)
        )


class MoveRoomInput(graphene.InputObjectType):
    room_id = graphene.ID(
        description="The ID of the room to move.", required=True
    )
    sort_order = graphene.Int(
        description=(
            "The relative sorting position of the room (from -inf to +inf) "
            "starting from the first given room's actual position."
            "1 moves the item one position forward, -1 moves the item one position "
            "backward, 0 leaves the item unchanged."
        )
    )


class CollectionReorderRooms(BaseMutation):
    collection = graphene.Field(
        Collection, description="Collection from which rooms are reordered."
    )

    class Meta:
        description = "Reorder the rooms of a collection."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = CollectionError
        error_type_field = "collection_errors"

    class Arguments:
        collection_id = graphene.Argument(
            graphene.ID, required=True, description="ID of a collection."
        )
        moves = graphene.List(
            MoveRoomInput,
            required=True,
            description="The collection rooms position operations.",
        )

    @classmethod
    def perform_mutation(cls, _root, info, collection_id, moves):
        pk = from_global_id_strict_type(
            collection_id, only_type=Collection, field="collection_id"
        )

        try:
            collection = models.Collection.objects.prefetch_related(
                "collectionroom"
            ).get(pk=pk)
        except ObjectDoesNotExist:
            raise ValidationError(
                {
                    "collection_id": ValidationError(
                        f"Couldn't resolve to a collection: {collection_id}",
                        code=RoomErrorCode.NOT_FOUND,
                    )
                }
            )

        m2m_related_field = collection.collectionroom

        operations = {}

        # Resolve the rooms
        for move_info in moves:
            room_pk = from_global_id_strict_type(
                move_info.room_id, only_type=Room, field="moves"
            )

            try:
                m2m_info = m2m_related_field.get(room_id=int(room_pk))
            except ObjectDoesNotExist:
                raise ValidationError(
                    {
                        "moves": ValidationError(
                            f"Couldn't resolve to a room: {move_info.room_id}",
                            code=CollectionErrorCode.NOT_FOUND.value,
                        )
                    }
                )
            operations[m2m_info.pk] = move_info.sort_order

        with transaction.atomic():
            perform_reordering(m2m_related_field, operations)
        collection = ChannelContext(node=collection, channel_slug=None)
        return CollectionReorderRooms(collection=collection)


class CollectionAddRooms(BaseMutation):
    collection = graphene.Field(
        Collection, description="Collection to which rooms will be added."
    )

    class Arguments:
        collection_id = graphene.Argument(
            graphene.ID, required=True, description="ID of a collection."
        )
        rooms = graphene.List(
            graphene.ID, required=True, description="List of room IDs."
        )

    class Meta:
        description = "Adds rooms to a collection."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = CollectionError
        error_type_field = "collection_errors"

    @classmethod
    @transaction.atomic()
    def perform_mutation(cls, _root, info, collection_id, rooms):
        collection = cls.get_node_or_error(
            info, collection_id, field="collection_id", only_type=Collection
        )
        rooms = cls.get_nodes_or_error(rooms, "rooms", Room)
        cls.clean_rooms(rooms)
        collection.rooms.add(*rooms)
        if collection.sale_set.exists():
            # Updated the db entries, recalculating discounts of affected rooms
            update_rooms_discounted_prices_of_catalogues_task.delay(
                room_ids=[pq.pk for pq in rooms]
            )
        return CollectionAddRooms(
            collection=ChannelContext(node=collection, channel_slug=None)
        )

    @classmethod
    def clean_rooms(cls, rooms):
        rooms_ids_without_variants = get_rooms_ids_without_variants(rooms)
        if rooms_ids_without_variants:
            code = CollectionErrorCode.CANNOT_MANAGE_ROOM_WITHOUT_VARIANT.value
            raise ValidationError(
                {
                    "rooms": ValidationError(
                        "Cannot manage rooms without variants.",
                        code=code,
                        params={"rooms": rooms_ids_without_variants},
                    )
                }
            )


class CollectionRemoveRooms(BaseMutation):
    collection = graphene.Field(
        Collection, description="Collection from which rooms will be removed."
    )

    class Arguments:
        collection_id = graphene.Argument(
            graphene.ID, required=True, description="ID of a collection."
        )
        rooms = graphene.List(
            graphene.ID, required=True, description="List of room IDs."
        )

    class Meta:
        description = "Remove rooms from a collection."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = CollectionError
        error_type_field = "collection_errors"

    @classmethod
    def perform_mutation(cls, _root, info, collection_id, rooms):
        collection = cls.get_node_or_error(
            info, collection_id, field="collection_id", only_type=Collection
        )
        rooms = cls.get_nodes_or_error(rooms, "rooms", only_type=Room)
        collection.rooms.remove(*rooms)
        if collection.sale_set.exists():
            # Updated the db entries, recalculating discounts of affected rooms
            update_rooms_discounted_prices_of_catalogues_task.delay(
                room_ids=[p.pk for p in rooms]
            )
        return CollectionRemoveRooms(
            collection=ChannelContext(node=collection, channel_slug=None)
        )


class AttributeValueInput(InputObjectType):
    id = graphene.ID(description="ID of the selected attribute.")
    values = graphene.List(
        graphene.String,
        required=False,
        description=(
            "The value or slug of an attribute to resolve. "
            "If the passed value is non-existent, it will be created."
        ),
    )
    file = graphene.String(
        required=False,
        description="URL of the file attribute. Every time, a new value is created.",
    )
    content_type = graphene.String(required=False, description="File content type.")


class RoomInput(graphene.InputObjectType):
    attributes = graphene.List(AttributeValueInput, description="List of attributes.")
    category = graphene.ID(description="ID of the room's category.", name="category")
    charge_taxes = graphene.Boolean(
        description="Determine if taxes are being charged for the room."
    )
    collections = graphene.List(
        graphene.ID,
        description="List of IDs of collections that the room belongs to.",
        name="collections",
    )
    description = graphene.String(description="Room description (HTML/text).")
    description_json = graphene.JSONString(description="Room description (JSON).")
    name = graphene.String(description="Room name.")
    slug = graphene.String(description="Room slug.")
    tax_code = graphene.String(description="Tax rate for enabled tax gateway.")
    seo = SeoInput(description="Search engine optimization fields.")
    weight = WeightScalar(description="Weight of the Room.", required=False)
    rating = graphene.Float(description="Defines the room rating value.")


class StockInput(graphene.InputObjectType):
    hotel = graphene.ID(
        required=True, description="Hotel in which stock is located."
    )
    quantity = graphene.Int(description="Quantity of items available for sell.")


class RoomCreateInput(RoomInput):
    room_type = graphene.ID(
        description="ID of the type that room belongs to.",
        name="roomType",
        required=True,
    )


T_INPUT_MAP = List[Tuple[attribute_models.Attribute, AttrValuesInput]]


class RoomCreate(ModelMutation):
    class Arguments:
        input = RoomCreateInput(
            required=True, description="Fields required to create a room."
        )

    class Meta:
        description = "Creates a new room."
        model = models.Room
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def clean_attributes(
        cls, attributes: dict, room_type: models.RoomType
    ) -> T_INPUT_MAP:
        attributes_qs = room_type.room_attributes
        attributes = AttributeAssignmentMixin.clean_input(
            attributes, attributes_qs, is_variant=False
        )
        return attributes

    @classmethod
    def clean_input(cls, info, instance, data):
        cleaned_input = super().clean_input(info, instance, data)

        weight = cleaned_input.get("weight")
        if weight and weight.value < 0:
            raise ValidationError(
                {
                    "weight": ValidationError(
                        "Room can't have negative weight.",
                        code=RoomErrorCode.INVALID.value,
                    )
                }
            )

        # Attributes are provided as list of `AttributeValueInput` objects.
        # We need to transform them into the format they're stored in the
        # `Room` model, which is HStore field that maps attribute's PK to
        # the value's PK.

        attributes = cleaned_input.get("attributes")
        room_type = (
            instance.room_type if instance.pk else cleaned_input.get("room_type")
        )  # type: models.RoomType

        try:
            cleaned_input = validate_slug_and_generate_if_needed(
                instance, "name", cleaned_input
            )
        except ValidationError as error:
            error.code = RoomErrorCode.REQUIRED.value
            raise ValidationError({"slug": error})

        # FIXME  tax_rate logic should be dropped after we remove tax_rate from input
        tax_rate = cleaned_input.pop("tax_rate", "")
        if tax_rate:
            info.context.plugins.assign_tax_code_to_object_meta(instance, tax_rate)

        if "tax_code" in cleaned_input:
            info.context.plugins.assign_tax_code_to_object_meta(
                instance, cleaned_input["tax_code"]
            )

        if attributes and room_type:
            try:
                cleaned_input["attributes"] = cls.clean_attributes(
                    attributes, room_type
                )
            except ValidationError as exc:
                raise ValidationError({"attributes": exc})

        clean_seo_fields(cleaned_input)
        return cleaned_input

    @classmethod
    def get_instance(cls, info, **data):
        """Prefetch related fields that are needed to process the mutation."""
        # If we are updating an instance and want to update its attributes,
        # prefetch them.

        object_id = data.get("id")
        if object_id and data.get("attributes"):
            # Prefetches needed by AttributeAssignmentMixin and
            # associate_attribute_values_to_instance
            qs = cls.Meta.model.objects.prefetch_related(
                "room_type__room_attributes__values",
                "room_type__attributeroom",
            )
            return cls.get_node_or_error(info, object_id, only_type="Room", qs=qs)

        return super().get_instance(info, **data)

    @classmethod
    @transaction.atomic
    def save(cls, info, instance, cleaned_input):
        instance.save()

        attributes = cleaned_input.get("attributes")
        if attributes:
            AttributeAssignmentMixin.save(instance, attributes)

    @classmethod
    def _save_m2m(cls, info, instance, cleaned_data):
        collections = cleaned_data.get("collections", None)
        if collections is not None:
            instance.collections.set(collections)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        response = super().perform_mutation(_root, info, **data)
        room = getattr(response, cls._meta.return_field_name)
        info.context.plugins.room_created(room)

        # Wrap room instance with ChannelContext in response
        setattr(
            response,
            cls._meta.return_field_name,
            ChannelContext(node=room, channel_slug=None),
        )
        return response


class RoomUpdate(RoomCreate):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a room to update.")
        input = RoomInput(
            required=True, description="Fields required to update a room."
        )

    class Meta:
        description = "Updates an existing room."
        model = models.Room
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    @transaction.atomic
    def save(cls, info, instance, cleaned_input):
        instance.save()
        attributes = cleaned_input.get("attributes")
        if attributes:
            AttributeAssignmentMixin.save(instance, attributes)
        info.context.plugins.room_updated(instance)


class RoomDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a room to delete.")

    class Meta:
        description = "Deletes a room."
        model = models.Room
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def success_response(cls, instance):
        instance = ChannelContext(node=instance, channel_slug=None)
        return super().success_response(instance)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        node_id = data.get("id")
        instance = cls.get_node_or_error(info, node_id, only_type=Room)

        # get draft order lines for variant
        line_pks = list(
            order_models.OrderLine.objects.filter(
                variant__in=instance.variants.all(), order__status=OrderStatus.DRAFT
            ).values_list("pk", flat=True)
        )

        response = super().perform_mutation(_root, info, **data)

        # delete order lines for deleted variant
        order_models.OrderLine.objects.filter(pk__in=line_pks).delete()

        return response


class RoomVariantInput(graphene.InputObjectType):
    attributes = graphene.List(
        AttributeValueInput,
        required=False,
        description="List of attributes specific to this variant.",
    )
    sku = graphene.String(description="Stock keeping unit.")
    track_inventory = graphene.Boolean(
        description=(
            "Determines if the inventory of this variant should be tracked. If false, "
            "the quantity won't change when customers buy this item."
        )
    )
    weight = WeightScalar(description="Weight of the Room Variant.", required=False)


class RoomVariantCreateInput(RoomVariantInput):
    attributes = graphene.List(
        AttributeValueInput,
        required=True,
        description="List of attributes specific to this variant.",
    )
    room = graphene.ID(
        description="Room ID of which type is the variant.",
        name="room",
        required=True,
    )
    stocks = graphene.List(
        graphene.NonNull(StockInput),
        description=("Stocks of a room available for sale."),
        required=False,
    )


class RoomVariantCreate(ModelMutation):
    class Arguments:
        input = RoomVariantCreateInput(
            required=True, description="Fields required to create a room variant."
        )

    class Meta:
        description = "Creates a new variant for a room."
        model = models.RoomVariant
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"
        errors_mapping = {"price_amount": "price"}

    @classmethod
    def clean_attributes(
        cls, attributes: dict, room_type: models.RoomType
    ) -> T_INPUT_MAP:
        attributes_qs = room_type.variant_attributes
        attributes = AttributeAssignmentMixin.clean_input(
            attributes, attributes_qs, is_variant=True
        )
        return attributes

    @classmethod
    def validate_duplicated_attribute_values(
        cls, attributes_data, used_attribute_values, instance=None
    ):
        attribute_values = defaultdict(list)
        for attr, attr_data in attributes_data:
            if attr.input_type == AttributeInputType.FILE:
                values = (
                    [slugify(attr_data.file_url.split("/")[-1])]
                    if attr_data.file_url
                    else []
                )
            else:
                values = attr_data.values
            attribute_values[attr_data.global_id].extend(values)
        if attribute_values in used_attribute_values:
            raise ValidationError(
                "Duplicated attribute values for room variant.",
                RoomErrorCode.DUPLICATED_INPUT_ITEM,
            )
        else:
            used_attribute_values.append(attribute_values)

    @classmethod
    def clean_input(
        cls, info, instance: models.RoomVariant, data: dict, input_cls=None
    ):
        cleaned_input = super().clean_input(info, instance, data)

        weight = cleaned_input.get("weight")
        if weight and weight.value < 0:
            raise ValidationError(
                {
                    "weight": ValidationError(
                        "Room variant can't have negative weight.",
                        code=RoomErrorCode.INVALID.value,
                    )
                }
            )

        stocks = cleaned_input.get("stocks")
        if stocks:
            cls.check_for_duplicates_in_stocks(stocks)

        if instance.pk:
            # If the variant is getting updated,
            # simply retrieve the associated room type
            room_type = instance.room.room_type
            used_attribute_values = get_used_variants_attribute_values(instance.room)
        else:
            # If the variant is getting created, no room type is associated yet,
            # retrieve it from the required "room" input field
            room_type = cleaned_input["room"].room_type
            used_attribute_values = get_used_variants_attribute_values(
                cleaned_input["room"]
            )

        # Run the validation only if room type is configurable
        if room_type.has_variants:
            # Attributes are provided as list of `AttributeValueInput` objects.
            # We need to transform them into the format they're stored in the
            # `Room` model, which is HStore field that maps attribute's PK to
            # the value's PK.
            attributes = cleaned_input.get("attributes")
            try:
                if attributes:
                    cleaned_attributes = cls.clean_attributes(attributes, room_type)
                    cls.validate_duplicated_attribute_values(
                        cleaned_attributes, used_attribute_values, instance
                    )
                    cleaned_input["attributes"] = cleaned_attributes
                elif not instance.pk and not attributes:
                    # if attributes were not provided on creation
                    raise ValidationError(
                        "All attributes must take a value.",
                        RoomErrorCode.REQUIRED.value,
                    )
            except ValidationError as exc:
                raise ValidationError({"attributes": exc})

        return cleaned_input

    @classmethod
    def check_for_duplicates_in_stocks(cls, stocks_data):
        hotel_ids = [stock["hotel"] for stock in stocks_data]
        duplicates = get_duplicated_values(hotel_ids)
        if duplicates:
            error_msg = "Duplicated hotel ID: {}".format(", ".join(duplicates))
            raise ValidationError(
                {
                    "stocks": ValidationError(
                        error_msg, code=RoomErrorCode.UNIQUE.value
                    )
                }
            )

    @classmethod
    def get_instance(cls, info, **data):
        """Prefetch related fields that are needed to process the mutation.

        If we are updating an instance and want to update its attributes,
        # prefetch them.
        """

        object_id = data.get("id")
        if object_id and data.get("attributes"):
            # Prefetches needed by AttributeAssignmentMixin and
            # associate_attribute_values_to_instance
            qs = cls.Meta.model.objects.prefetch_related(
                "room__room_type__variant_attributes__values",
                "room__room_type__attributevariant",
            )
            return cls.get_node_or_error(
                info, object_id, only_type="RoomVariant", qs=qs
            )

        return super().get_instance(info, **data)

    @classmethod
    @transaction.atomic()
    def save(cls, info, instance, cleaned_input):
        instance.save()
        if not instance.room.default_variant:
            instance.room.default_variant = instance
            instance.room.save(update_fields=["default_variant", "updated_at"])
        # Recalculate the "discounted price" for the parent room
        update_room_discounted_price_task.delay(instance.room_id)
        stocks = cleaned_input.get("stocks")
        if stocks:
            cls.create_variant_stocks(instance, stocks)

        attributes = cleaned_input.get("attributes")
        if attributes:
            AttributeAssignmentMixin.save(instance, attributes)
            generate_and_set_variant_name(instance, cleaned_input.get("sku"))
        info.context.plugins.room_updated(instance.room)

    @classmethod
    def create_variant_stocks(cls, variant, stocks):
        hotel_ids = [stock["hotel"] for stock in stocks]
        hotels = cls.get_nodes_or_error(
            hotel_ids, "hotel", only_type=Hotel
        )
        create_stocks(variant, stocks, hotels)

    @classmethod
    def success_response(cls, instance):
        instance = ChannelContext(node=instance, channel_slug=None)
        return super().success_response(instance)


class RoomVariantUpdate(RoomVariantCreate):
    class Arguments:
        id = graphene.ID(
            required=True, description="ID of a room variant to update."
        )
        input = RoomVariantInput(
            required=True, description="Fields required to update a room variant."
        )

    class Meta:
        description = "Updates an existing variant for room."
        model = models.RoomVariant
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"
        errors_mapping = {"price_amount": "price"}

    @classmethod
    def validate_duplicated_attribute_values(
        cls, attributes_data, used_attribute_values, instance=None
    ):
        # Check if the variant is getting updated,
        # and the assigned attributes do not change
        if instance.room_id is not None:
            assigned_attributes = get_used_attribute_values_for_variant(instance)
            input_attribute_values = defaultdict(list)
            for attr, attr_data in attributes_data:
                if attr.input_type == AttributeInputType.FILE:
                    values = (
                        [slugify(attr_data.file_url.split("/")[-1])]
                        if attr_data.file_url
                        else []
                    )
                else:
                    values = attr_data.values
                input_attribute_values[attr_data.global_id].extend(values)
            if input_attribute_values == assigned_attributes:
                return
        # if assigned attributes is getting updated run duplicated attribute validation
        super().validate_duplicated_attribute_values(
            attributes_data, used_attribute_values
        )


class RoomVariantDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(
            required=True, description="ID of a room variant to delete."
        )

    class Meta:
        description = "Deletes a room variant."
        model = models.RoomVariant
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def success_response(cls, instance):
        # Update the "discounted_prices" of the parent room
        update_room_discounted_price_task.delay(instance.room_id)
        room = models.Room.objects.get(id=instance.room_id)
        # if the room default variant has been removed set the new one
        if not room.default_variant:
            room.default_variant = room.variants.first()
            room.save(update_fields=["default_variant"])
        instance = ChannelContext(node=instance, channel_slug=None)
        return super().success_response(instance)

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        node_id = data.get("id")
        variant_pk = from_global_id_strict_type(node_id, RoomVariant, field="pk")

        # get draft order lines for variant
        line_pks = list(
            order_models.OrderLine.objects.filter(
                variant__pk=variant_pk, order__status=OrderStatus.DRAFT
            ).values_list("pk", flat=True)
        )

        response = super().perform_mutation(_root, info, **data)

        # delete order lines for deleted variant
        order_models.OrderLine.objects.filter(pk__in=line_pks).delete()

        return response


class RoomTypeInput(graphene.InputObjectType):
    name = graphene.String(description="Name of the room type.")
    slug = graphene.String(description="Room type slug.")
    has_variants = graphene.Boolean(
        description=(
            "Determines if room of this type has multiple variants. This option "
            "mainly simplifies room management in the dashboard. There is always at "
            "least one variant created under the hood."
        )
    )
    room_attributes = graphene.List(
        graphene.ID,
        description="List of attributes shared among all room variants.",
        name="roomAttributes",
    )
    variant_attributes = graphene.List(
        graphene.ID,
        description=(
            "List of attributes used to distinguish between different variants of "
            "a room."
        ),
        name="variantAttributes",
    )
    is_shipping_required = graphene.Boolean(
        description="Determines if shipping is required for rooms of this variant."
    )
    is_digital = graphene.Boolean(
        description="Determines if rooms are digital.", required=False
    )
    weight = WeightScalar(description="Weight of the RoomType items.")
    tax_code = graphene.String(description="Tax rate for enabled tax gateway.")


class RoomTypeCreate(ModelMutation):
    class Arguments:
        input = RoomTypeInput(
            required=True, description="Fields required to create a room type."
        )

    class Meta:
        description = "Creates a new room type."
        model = models.RoomType
        permissions = (RoomTypePermissions.MANAGE_ROOM_TYPES_AND_ATTRIBUTES,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def clean_input(cls, info, instance, data):
        cleaned_input = super().clean_input(info, instance, data)

        weight = cleaned_input.get("weight")
        if weight and weight.value < 0:
            raise ValidationError(
                {
                    "weight": ValidationError(
                        "Room type can't have negative weight.",
                        code=RoomErrorCode.INVALID,
                    )
                }
            )

        try:
            cleaned_input = validate_slug_and_generate_if_needed(
                instance, "name", cleaned_input
            )
        except ValidationError as error:
            error.code = RoomErrorCode.REQUIRED.value
            raise ValidationError({"slug": error})

        # FIXME  tax_rate logic should be dropped after we remove tax_rate from input
        tax_rate = cleaned_input.pop("tax_rate", "")
        if tax_rate:
            instance.store_value_in_metadata(
                {"vatlayer.code": tax_rate, "description": tax_rate}
            )
            info.context.plugins.assign_tax_code_to_object_meta(instance, tax_rate)

        tax_code = cleaned_input.pop("tax_code", "")
        if tax_code:
            info.context.plugins.assign_tax_code_to_object_meta(instance, tax_code)

        cls.validate_attributes(cleaned_input)

        return cleaned_input

    @classmethod
    def validate_attributes(cls, cleaned_data):
        errors = {}
        for field in ["room_attributes", "variant_attributes"]:
            attributes = cleaned_data.get(field)
            if not attributes:
                continue
            not_valid_attributes = [
                graphene.Node.to_global_id("Attribute", attr.pk)
                for attr in attributes
                if attr.type != AttributeType.ROOM_TYPE
            ]
            if not_valid_attributes:
                errors[field] = ValidationError(
                    "Only Room type attributes are allowed.",
                    code=RoomErrorCode.INVALID.value,
                    params={"attributes": not_valid_attributes},
                )
        if errors:
            raise ValidationError(errors)

    @classmethod
    def _save_m2m(cls, info, instance, cleaned_data):
        super()._save_m2m(info, instance, cleaned_data)
        room_attributes = cleaned_data.get("room_attributes")
        variant_attributes = cleaned_data.get("variant_attributes")
        if room_attributes is not None:
            instance.room_attributes.set(room_attributes)
        if variant_attributes is not None:
            instance.variant_attributes.set(variant_attributes)


class RoomTypeUpdate(RoomTypeCreate):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a room type to update.")
        input = RoomTypeInput(
            required=True, description="Fields required to update a room type."
        )

    class Meta:
        description = "Updates an existing room type."
        model = models.RoomType
        permissions = (RoomTypePermissions.MANAGE_ROOM_TYPES_AND_ATTRIBUTES,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def save(cls, info, instance, cleaned_input):
        variant_attr = cleaned_input.get("variant_attributes")
        if variant_attr:
            variant_attr = set(variant_attr)
            variant_attr_ids = [attr.pk for attr in variant_attr]
            update_variants_names.delay(instance.pk, variant_attr_ids)
        super().save(info, instance, cleaned_input)


class RoomTypeDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a room type to delete.")

    class Meta:
        description = "Deletes a room type."
        model = models.RoomType
        permissions = (RoomTypePermissions.MANAGE_ROOM_TYPES_AND_ATTRIBUTES,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        node_id = data.get("id")
        room_type_pk = from_global_id_strict_type(node_id, RoomType, field="pk")
        variants_pks = models.Room.objects.filter(
            room_type__pk=room_type_pk
        ).values_list("variants__pk", flat=True)
        # get draft order lines for rooms
        order_line_pks = list(
            order_models.OrderLine.objects.filter(
                variant__pk__in=variants_pks, order__status=OrderStatus.DRAFT
            ).values_list("pk", flat=True)
        )

        response = super().perform_mutation(_root, info, **data)

        # delete order lines for deleted variants
        order_models.OrderLine.objects.filter(pk__in=order_line_pks).delete()

        return response


class RoomImageCreateInput(graphene.InputObjectType):
    alt = graphene.String(description="Alt text for an image.")
    image = Upload(
        required=True, description="Represents an image file in a multipart request."
    )
    room = graphene.ID(
        required=True, description="ID of an room.", name="room"
    )


class RoomImageCreate(BaseMutation):
    room = graphene.Field(Room)
    image = graphene.Field(RoomImage)

    class Arguments:
        input = RoomImageCreateInput(
            required=True, description="Fields required to create a room image."
        )

    class Meta:
        description = (
            "Create a room image. This mutation must be sent as a `multipart` "
            "request. More detailed specs of the upload format can be found here: "
            "https://github.com/jaydenseric/graphql-multipart-request-spec"
        )
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        data = data.get("input")
        room = cls.get_node_or_error(
            info, data["room"], field="room", only_type=Room
        )

        image_data = info.context.FILES.get(data["image"])
        validate_image_file(image_data, "image")

        image = room.images.create(image=image_data, alt=data.get("alt", ""))
        create_room_thumbnails.delay(image.pk)
        room = ChannelContext(node=room, channel_slug=None)
        return RoomImageCreate(room=room, image=image)


class RoomImageUpdateInput(graphene.InputObjectType):
    alt = graphene.String(description="Alt text for an image.")


class RoomImageUpdate(BaseMutation):
    room = graphene.Field(Room)
    image = graphene.Field(RoomImage)

    class Arguments:
        id = graphene.ID(required=True, description="ID of a room image to update.")
        input = RoomImageUpdateInput(
            required=True, description="Fields required to update a room image."
        )

    class Meta:
        description = "Updates a room image."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        image = cls.get_node_or_error(info, data.get("id"), only_type=RoomImage)
        room = image.room
        alt = data.get("input").get("alt")
        if alt is not None:
            image.alt = alt
            image.save(update_fields=["alt"])
        room = ChannelContext(node=room, channel_slug=None)
        return RoomImageUpdate(room=room, image=image)


class RoomImageReorder(BaseMutation):
    room = graphene.Field(Room)
    images = graphene.List(RoomImage)

    class Arguments:
        room_id = graphene.ID(
            required=True,
            description="Id of room that images order will be altered.",
        )
        images_ids = graphene.List(
            graphene.ID,
            required=True,
            description="IDs of a room images in the desired order.",
        )

    class Meta:
        description = "Changes ordering of the room image."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def perform_mutation(cls, _root, info, room_id, images_ids):
        room = cls.get_node_or_error(
            info, room_id, field="room_id", only_type=Room
        )
        if len(images_ids) != room.images.count():
            raise ValidationError(
                {
                    "order": ValidationError(
                        "Incorrect number of image IDs provided.",
                        code=RoomErrorCode.INVALID,
                    )
                }
            )

        images = []
        for image_id in images_ids:
            image = cls.get_node_or_error(
                info, image_id, field="order", only_type=RoomImage
            )
            if image and image.room != room:
                raise ValidationError(
                    {
                        "order": ValidationError(
                            "Image %(image_id)s does not belong to this room.",
                            code=RoomErrorCode.NOT_ROOMS_IMAGE,
                            params={"image_id": image_id},
                        )
                    }
                )
            images.append(image)

        for order, image in enumerate(images):
            image.sort_order = order
            image.save(update_fields=["sort_order"])

        room = ChannelContext(node=room, channel_slug=None)
        return RoomImageReorder(room=room, images=images)


class RoomVariantSetDefault(BaseMutation):
    room = graphene.Field(Room)

    class Arguments:
        room_id = graphene.ID(
            required=True,
            description="Id of a room that will have the default variant set.",
        )
        variant_id = graphene.ID(
            required=True,
            description="Id of a variant that will be set as default.",
        )

    class Meta:
        description = (
            "Set default variant for a room. "
            "Mutation triggers ROOM_UPDATED webhook."
        )
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def perform_mutation(cls, _root, info, room_id, variant_id):
        room = cls.get_node_or_error(
            info, room_id, field="room_id", only_type=Room
        )
        variant = cls.get_node_or_error(
            info,
            variant_id,
            field="variant_id",
            only_type=RoomVariant,
            qs=models.RoomVariant.objects.select_related("room"),
        )
        if variant.room != room:
            raise ValidationError(
                {
                    "variant_id": ValidationError(
                        "Provided variant doesn't belong to provided room.",
                        code=RoomErrorCode.NOT_ROOMS_VARIANT,
                    )
                }
            )
        room.default_variant = variant
        room.save(update_fields=["default_variant", "updated_at"])
        info.context.plugins.room_updated(room)
        room = ChannelContext(node=room, channel_slug=None)
        return RoomVariantSetDefault(room=room)


class RoomVariantReorder(BaseMutation):
    room = graphene.Field(Room)

    class Arguments:
        room_id = graphene.ID(
            required=True,
            description="Id of room that variants order will be altered.",
        )
        moves = graphene.List(
            ReorderInput,
            required=True,
            description="The list of variant reordering operations.",
        )

    class Meta:
        description = (
            "Reorder the variants of a room. "
            "Mutation updates updated_at on room and "
            "triggers ROOM_UPDATED webhook."
        )
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def perform_mutation(cls, _root, info, room_id, moves):
        pk = from_global_id_strict_type(room_id, only_type=Room, field="id")

        try:
            room = models.Room.objects.prefetch_related("variants").get(pk=pk)
        except ObjectDoesNotExist:
            raise ValidationError(
                {
                    "room_id": ValidationError(
                        (f"Couldn't resolve to a room type: {room_id}"),
                        code=RoomErrorCode.NOT_FOUND,
                    )
                }
            )

        variants_m2m = room.variants
        operations = {}

        for move_info in moves:
            variant_pk = from_global_id_strict_type(
                move_info.id, only_type=RoomVariant, field="moves"
            )

            try:
                m2m_info = variants_m2m.get(id=int(variant_pk))
            except ObjectDoesNotExist:
                raise ValidationError(
                    {
                        "moves": ValidationError(
                            f"Couldn't resolve to a variant: {move_info.id}",
                            code=RoomErrorCode.NOT_FOUND,
                        )
                    }
                )
            operations[m2m_info.pk] = move_info.sort_order

        with transaction.atomic():
            perform_reordering(variants_m2m, operations)

        room.save(update_fields=["updated_at"])
        info.context.plugins.room_updated(room)
        room = ChannelContext(node=room, channel_slug=None)
        return RoomVariantReorder(room=room)


class RoomImageDelete(BaseMutation):
    room = graphene.Field(Room)
    image = graphene.Field(RoomImage)

    class Arguments:
        id = graphene.ID(required=True, description="ID of a room image to delete.")

    class Meta:
        description = "Deletes a room image."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        image = cls.get_node_or_error(info, data.get("id"), only_type=RoomImage)
        image_id = image.id
        image.delete()
        image.id = image_id
        room = ChannelContext(node=image.room, channel_slug=None)
        return RoomImageDelete(room=room, image=image)


class VariantImageAssign(BaseMutation):
    room_variant = graphene.Field(RoomVariant)
    image = graphene.Field(RoomImage)

    class Arguments:
        image_id = graphene.ID(
            required=True, description="ID of a room image to assign to a variant."
        )
        variant_id = graphene.ID(required=True, description="ID of a room variant.")

    class Meta:
        description = "Assign an image to a room variant."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def perform_mutation(cls, _root, info, image_id, variant_id):
        image = cls.get_node_or_error(
            info, image_id, field="image_id", only_type=RoomImage
        )
        variant = cls.get_node_or_error(
            info, variant_id, field="variant_id", only_type=RoomVariant
        )
        if image and variant:
            # check if the given image and variant can be matched together
            image_belongs_to_room = variant.room.images.filter(
                pk=image.pk
            ).first()
            if image_belongs_to_room:
                image.variant_images.create(variant=variant)
            else:
                raise ValidationError(
                    {
                        "image_id": ValidationError(
                            "This image doesn't belong to that room.",
                            code=RoomErrorCode.NOT_ROOMS_IMAGE,
                        )
                    }
                )
        variant = ChannelContext(node=variant, channel_slug=None)
        return VariantImageAssign(room_variant=variant, image=image)


class VariantImageUnassign(BaseMutation):
    room_variant = graphene.Field(RoomVariant)
    image = graphene.Field(RoomImage)

    class Arguments:
        image_id = graphene.ID(
            required=True,
            description="ID of a room image to unassign from a variant.",
        )
        variant_id = graphene.ID(required=True, description="ID of a room variant.")

    class Meta:
        description = "Unassign an image from a room variant."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def perform_mutation(cls, _root, info, image_id, variant_id):
        image = cls.get_node_or_error(
            info, image_id, field="image_id", only_type=RoomImage
        )
        variant = cls.get_node_or_error(
            info, variant_id, field="variant_id", only_type=RoomVariant
        )

        try:
            variant_image = models.VariantImage.objects.get(
                image=image, variant=variant
            )
        except models.VariantImage.DoesNotExist:
            raise ValidationError(
                {
                    "image_id": ValidationError(
                        "Image is not assigned to this variant.",
                        code=RoomErrorCode.NOT_ROOMS_IMAGE,
                    )
                }
            )
        else:
            variant_image.delete()

        variant = ChannelContext(node=variant, channel_slug=None)
        return VariantImageUnassign(room_variant=variant, image=image)
