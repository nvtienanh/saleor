from collections import defaultdict

import graphene
from django.core.exceptions import ValidationError
from django.db import transaction
from graphene.types import InputObjectType

from ....core.permissions import RoomPermissions, RoomTypePermissions
from ....order import OrderStatus
from ....order import models as order_models
from ....room import models
from ....room.error_codes import RoomErrorCode
from ....room.tasks import update_room_discounted_price_task
from ....room.utils import delete_categories
from ....room.utils.variants import generate_and_set_variant_name
from ....hotel import models as hotel_models
from ....hotel.error_codes import StockErrorCode
from ...channel import ChannelContext
from ...channel.types import Channel
from ...core.mutations import BaseMutation, ModelBulkDeleteMutation, ModelMutation
from ...core.types.common import (
    BulkRoomError,
    BulkStockError,
    RoomError,
    StockError,
)
from ...core.utils import get_duplicated_values
from ...core.validators import validate_price_precision
from ...utils import resolve_global_ids_to_primary_keys
from ...hotel.types import Hotel
from ..mutations.channels import RoomVariantChannelListingAddInput
from ..mutations.rooms import (
    AttributeAssignmentMixin,
    RoomVariantCreate,
    RoomVariantInput,
    StockInput,
)
from ..types import Room, RoomVariant
from ..utils import create_stocks, get_used_variants_attribute_values


class CategoryBulkDelete(ModelBulkDeleteMutation):
    class Arguments:
        ids = graphene.List(
            graphene.ID, required=True, description="List of category IDs to delete."
        )

    class Meta:
        description = "Deletes categories."
        model = models.Category
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def bulk_action(cls, queryset):
        delete_categories(queryset.values_list("pk", flat=True))


class CollectionBulkDelete(ModelBulkDeleteMutation):
    class Arguments:
        ids = graphene.List(
            graphene.ID, required=True, description="List of collection IDs to delete."
        )

    class Meta:
        description = "Deletes collections."
        model = models.Collection
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"


class RoomBulkDelete(ModelBulkDeleteMutation):
    class Arguments:
        ids = graphene.List(
            graphene.ID, required=True, description="List of room IDs to delete."
        )

    class Meta:
        description = "Deletes rooms."
        model = models.Room
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    def perform_mutation(cls, _root, info, ids, **data):
        _, pks = resolve_global_ids_to_primary_keys(ids, Room)
        variants = models.RoomVariant.objects.filter(room__pk__in=pks)
        # get draft order lines for rooms
        order_line_pks = list(
            order_models.OrderLine.objects.filter(
                variant__in=variants, order__status=OrderStatus.DRAFT
            ).values_list("pk", flat=True)
        )

        response = super().perform_mutation(_root, info, ids, **data)

        # delete order lines for deleted variants
        order_models.OrderLine.objects.filter(pk__in=order_line_pks).delete()

        return response


class BulkAttributeValueInput(InputObjectType):
    id = graphene.ID(description="ID of the selected attribute.")
    values = graphene.List(
        graphene.String,
        required=True,
        description=(
            "The value or slug of an attribute to resolve. "
            "If the passed value is non-existent, it will be created."
        ),
    )


class RoomVariantBulkCreateInput(RoomVariantInput):
    attributes = graphene.List(
        BulkAttributeValueInput,
        required=True,
        description="List of attributes specific to this variant.",
    )
    stocks = graphene.List(
        graphene.NonNull(StockInput),
        description=("Stocks of a room available for sale."),
        required=False,
    )
    channel_listings = graphene.List(
        graphene.NonNull(RoomVariantChannelListingAddInput),
        description="List of prices assigned to channels.",
        required=False,
    )
    sku = graphene.String(required=True, description="Stock keeping unit.")


class RoomVariantBulkCreate(BaseMutation):
    count = graphene.Int(
        required=True,
        default_value=0,
        description="Returns how many objects were created.",
    )
    room_variants = graphene.List(
        graphene.NonNull(RoomVariant),
        required=True,
        default_value=[],
        description="List of the created variants.",
    )

    class Arguments:
        variants = graphene.List(
            RoomVariantBulkCreateInput,
            required=True,
            description="Input list of room variants to create.",
        )
        room_id = graphene.ID(
            description="ID of the room to create the variants for.",
            name="room",
            required=True,
        )

    class Meta:
        description = "Creates room variants for a given room."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = BulkRoomError
        error_type_field = "bulk_room_errors"

    @classmethod
    def clean_variant_input(
        cls,
        info,
        instance: models.RoomVariant,
        data: dict,
        errors: dict,
        variant_index: int,
    ):
        cleaned_input = ModelMutation.clean_input(
            info, instance, data, input_cls=RoomVariantBulkCreateInput
        )

        attributes = cleaned_input.get("attributes")
        if attributes:
            try:
                cleaned_input["attributes"] = RoomVariantCreate.clean_attributes(
                    attributes, data["room_type"]
                )
            except ValidationError as exc:
                exc.params = {"index": variant_index}
                errors["attributes"] = exc

        channel_listings = cleaned_input.get("channel_listings")
        if channel_listings:
            cleaned_input["channel_listings"] = cls.clean_channel_listings(
                channel_listings, errors, data["room"], variant_index
            )

        stocks = cleaned_input.get("stocks")
        if stocks:
            cls.clean_stocks(stocks, errors, variant_index)

        return cleaned_input

    @classmethod
    def clean_price(
        cls, price, field_name, currency, channel_id, variant_index, errors
    ):
        try:
            validate_price_precision(price, currency)
        except ValidationError as error:
            error.code = RoomErrorCode.INVALID.value
            error.params = {
                "channels": [channel_id],
                "index": variant_index,
            }
            errors[field_name].append(error)

    @classmethod
    def clean_channel_listings(cls, channels_data, errors, room, variant_index):
        channel_ids = [
            channel_listing["channel_id"] for channel_listing in channels_data
        ]
        duplicates = get_duplicated_values(channel_ids)
        if duplicates:
            errors["channel_listings"] = ValidationError(
                "Duplicated channel ID.",
                code=RoomErrorCode.DUPLICATED_INPUT_ITEM.value,
                params={"channels": duplicates, "index": variant_index},
            )
            return channels_data
        channels = cls.get_nodes_or_error(
            channel_ids, "channel_listings", only_type=Channel
        )
        for index, channel_listing_data in enumerate(channels_data):
            channel_listing_data["channel"] = channels[index]

        for channel_listing_data in channels_data:
            price = channel_listing_data.get("price")
            cost_price = channel_listing_data.get("cost_price")
            channel_id = channel_listing_data["channel_id"]
            currency_code = channel_listing_data["channel"].currency_code
            cls.clean_price(
                price, "price", currency_code, channel_id, variant_index, errors
            )
            cls.clean_price(
                cost_price,
                "cost_price",
                currency_code,
                channel_id,
                variant_index,
                errors,
            )

        channels_not_assigned_to_room = []
        channels_assigned_to_room = list(
            models.RoomChannelListing.objects.filter(room=room.id).values_list(
                "channel_id", flat=True
            )
        )
        for channel_listing_data in channels_data:
            if not channel_listing_data["channel"].id in channels_assigned_to_room:
                channels_not_assigned_to_room.append(
                    channel_listing_data["channel_id"]
                )
        if channels_not_assigned_to_room:
            errors["channel_id"].append(
                ValidationError(
                    "Room not available in channels.",
                    code=RoomErrorCode.ROOM_NOT_ASSIGNED_TO_CHANNEL.value,
                    params={
                        "index": variant_index,
                        "channels": channels_not_assigned_to_room,
                    },
                )
            )
        return channels_data

    @classmethod
    def clean_stocks(cls, stocks_data, errors, variant_index):
        hotel_ids = [stock["hotel"] for stock in stocks_data]
        duplicates = get_duplicated_values(hotel_ids)
        if duplicates:
            errors["stocks"] = ValidationError(
                "Duplicated hotel ID.",
                code=RoomErrorCode.DUPLICATED_INPUT_ITEM.value,
                params={"hotels": duplicates, "index": variant_index},
            )

    @classmethod
    def add_indexes_to_errors(cls, index, error, error_dict):
        """Append errors with index in params to mutation error dict."""
        for key, value in error.error_dict.items():
            for e in value:
                if e.params:
                    e.params["index"] = index
                else:
                    e.params = {"index": index}
            error_dict[key].extend(value)

    @classmethod
    def save(cls, info, instance, cleaned_input):
        instance.save()

        attributes = cleaned_input.get("attributes")
        if attributes:
            AttributeAssignmentMixin.save(instance, attributes)
            generate_and_set_variant_name(instance, cleaned_input.get("sku"))

    @classmethod
    def create_variants(cls, info, cleaned_inputs, room, errors):
        instances = []
        for index, cleaned_input in enumerate(cleaned_inputs):
            if not cleaned_input:
                continue
            try:
                instance = models.RoomVariant()
                cleaned_input["room"] = room
                instance = cls.construct_instance(instance, cleaned_input)
                cls.clean_instance(info, instance)
                instances.append(instance)
            except ValidationError as exc:
                cls.add_indexes_to_errors(index, exc, errors)
        return instances

    @classmethod
    def validate_duplicated_sku(cls, sku, index, sku_list, errors):
        if sku in sku_list:
            errors["sku"].append(
                ValidationError(
                    "Duplicated SKU.", RoomErrorCode.UNIQUE, params={"index": index}
                )
            )
        sku_list.append(sku)

    @classmethod
    def validate_duplicated_attribute_values(
        cls, attributes_data, used_attribute_values, instance=None
    ):
        attribute_values = defaultdict(list)
        for attr in attributes_data:
            attribute_values[attr.id].extend(attr.values)
        if attribute_values in used_attribute_values:
            raise ValidationError(
                "Duplicated attribute values for room variant.",
                RoomErrorCode.DUPLICATED_INPUT_ITEM,
            )
        used_attribute_values.append(attribute_values)

    @classmethod
    def clean_variants(cls, info, variants, room, errors):
        cleaned_inputs = []
        sku_list = []
        used_attribute_values = get_used_variants_attribute_values(room)
        for index, variant_data in enumerate(variants):
            try:
                cls.validate_duplicated_attribute_values(
                    variant_data.attributes, used_attribute_values
                )
            except ValidationError as exc:
                errors["attributes"].append(
                    ValidationError(exc.message, exc.code, params={"index": index})
                )

            cleaned_input = None
            variant_data["room_type"] = room.room_type
            variant_data["room"] = room
            cleaned_input = cls.clean_variant_input(
                info, None, variant_data, errors, index
            )

            cleaned_inputs.append(cleaned_input if cleaned_input else None)

            if not variant_data.sku:
                continue
            cls.validate_duplicated_sku(variant_data.sku, index, sku_list, errors)
        return cleaned_inputs

    @classmethod
    def create_variant_channel_listings(cls, variant, cleaned_input):
        channel_listings_data = cleaned_input.get("channel_listings")
        if not channel_listings_data:
            return
        variant_channel_listings = []
        for channel_listing_data in channel_listings_data:
            channel = channel_listing_data["channel"]
            price = channel_listing_data["price"]
            cost_price = channel_listing_data.get("cost_price")
            variant_channel_listings.append(
                models.RoomVariantChannelListing(
                    channel=channel,
                    variant=variant,
                    price_amount=price,
                    cost_price_amount=cost_price,
                    currency=channel.currency_code,
                )
            )
        models.RoomVariantChannelListing.objects.bulk_create(
            variant_channel_listings
        )

    @classmethod
    @transaction.atomic
    def save_variants(cls, info, instances, room, cleaned_inputs):
        assert len(instances) == len(
            cleaned_inputs
        ), "There should be the same number of instances and cleaned inputs."
        for instance, cleaned_input in zip(instances, cleaned_inputs):
            cls.save(info, instance, cleaned_input)
            cls.create_variant_stocks(instance, cleaned_input)
            cls.create_variant_channel_listings(instance, cleaned_input)
        if not room.default_variant:
            room.default_variant = instances[0]
            room.save(update_fields=["default_variant", "updated_at"])

    @classmethod
    def create_variant_stocks(cls, variant, cleaned_input):
        stocks = cleaned_input.get("stocks")
        if not stocks:
            return
        hotel_ids = [stock["hotel"] for stock in stocks]
        hotels = cls.get_nodes_or_error(
            hotel_ids, "hotel", only_type=Hotel
        )
        create_stocks(variant, stocks, hotels)

    @classmethod
    def perform_mutation(cls, root, info, **data):
        room = cls.get_node_or_error(info, data["room_id"], models.Room)
        errors = defaultdict(list)

        cleaned_inputs = cls.clean_variants(info, data["variants"], room, errors)
        instances = cls.create_variants(info, cleaned_inputs, room, errors)
        if errors:
            raise ValidationError(errors)
        cls.save_variants(info, instances, room, cleaned_inputs)

        # Recalculate the "discounted price" for the parent room
        update_room_discounted_price_task.delay(room.pk)

        instances = [
            ChannelContext(node=instance, channel_slug=None) for instance in instances
        ]
        return RoomVariantBulkCreate(
            count=len(instances), room_variants=instances
        )


class RoomVariantBulkDelete(ModelBulkDeleteMutation):
    class Arguments:
        ids = graphene.List(
            graphene.ID,
            required=True,
            description="List of room variant IDs to delete.",
        )

    class Meta:
        description = "Deletes room variants."
        model = models.RoomVariant
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"

    @classmethod
    @transaction.atomic
    def perform_mutation(cls, _root, info, ids, **data):
        _, pks = resolve_global_ids_to_primary_keys(ids, RoomVariant)
        # get draft order lines for variants
        order_line_pks = list(
            order_models.OrderLine.objects.filter(
                variant__pk__in=pks, order__status=OrderStatus.DRAFT
            ).values_list("pk", flat=True)
        )

        room_pks = list(
            models.Room.objects.filter(variants__in=pks)
            .distinct()
            .values_list("pk", flat=True)
        )

        response = super().perform_mutation(_root, info, ids, **data)

        # delete order lines for deleted variants
        order_models.OrderLine.objects.filter(pk__in=order_line_pks).delete()

        # set new room default variant if any has been removed
        rooms = models.Room.objects.filter(
            pk__in=room_pks, default_variant__isnull=True
        )
        for room in rooms:
            room.default_variant = room.variants.first()
            room.save(update_fields=["default_variant"])

        return response


class RoomVariantStocksCreate(BaseMutation):
    room_variant = graphene.Field(
        RoomVariant, description="Updated room variant."
    )

    class Arguments:
        variant_id = graphene.ID(
            required=True,
            description="ID of a room variant for which stocks will be created.",
        )
        stocks = graphene.List(
            graphene.NonNull(StockInput),
            required=True,
            description="Input list of stocks to create.",
        )

    class Meta:
        description = "Creates stocks for room variant."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = BulkStockError
        error_type_field = "bulk_stock_errors"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        errors = defaultdict(list)
        stocks = data["stocks"]
        variant = cls.get_node_or_error(
            info, data["variant_id"], only_type=RoomVariant
        )
        if stocks:
            hotels = cls.clean_stocks_input(variant, stocks, errors)
            if errors:
                raise ValidationError(errors)
            create_stocks(variant, stocks, hotels)

        variant = ChannelContext(node=variant, channel_slug=None)
        return cls(room_variant=variant)

    @classmethod
    def clean_stocks_input(cls, variant, stocks_data, errors):
        hotel_ids = [stock["hotel"] for stock in stocks_data]
        cls.check_for_duplicates(hotel_ids, errors)
        hotels = cls.get_nodes_or_error(
            hotel_ids, "hotel", only_type=Hotel
        )
        existing_stocks = variant.stocks.filter(hotel__in=hotels).values_list(
            "hotel__pk", flat=True
        )
        error_msg = "Stock for this hotel already exists for this room variant."
        indexes = []
        for hotel_pk in existing_stocks:
            hotel_id = graphene.Node.to_global_id("Hotel", hotel_pk)
            indexes.extend(
                [i for i, id in enumerate(hotel_ids) if id == hotel_id]
            )
        cls.update_errors(
            errors, error_msg, "hotel", StockErrorCode.UNIQUE, indexes
        )

        return hotels

    @classmethod
    def check_for_duplicates(cls, hotel_ids, errors):
        duplicates = {id for id in hotel_ids if hotel_ids.count(id) > 1}
        error_msg = "Duplicated hotel ID."
        indexes = []
        for duplicated_id in duplicates:
            indexes.append(
                [i for i, id in enumerate(hotel_ids) if id == duplicated_id][-1]
            )
        cls.update_errors(
            errors, error_msg, "hotel", StockErrorCode.UNIQUE, indexes
        )

    @classmethod
    def update_errors(cls, errors, msg, field, code, indexes):
        for index in indexes:
            error = ValidationError(msg, code=code, params={"index": index})
            errors[field].append(error)


class RoomVariantStocksUpdate(RoomVariantStocksCreate):
    class Meta:
        description = "Update stocks for room variant."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = BulkStockError
        error_type_field = "bulk_stock_errors"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        errors = defaultdict(list)
        stocks = data["stocks"]
        variant = cls.get_node_or_error(
            info, data["variant_id"], only_type=RoomVariant
        )
        if stocks:
            hotel_ids = [stock["hotel"] for stock in stocks]
            cls.check_for_duplicates(hotel_ids, errors)
            if errors:
                raise ValidationError(errors)
            hotels = cls.get_nodes_or_error(
                hotel_ids, "hotel", only_type=Hotel
            )
            cls.update_or_create_variant_stocks(variant, stocks, hotels)

        variant = ChannelContext(node=variant, channel_slug=None)
        return cls(room_variant=variant)

    @classmethod
    @transaction.atomic
    def update_or_create_variant_stocks(cls, variant, stocks_data, hotels):
        stocks = []
        for stock_data, hotel in zip(stocks_data, hotels):
            stock, _ = hotel_models.Stock.objects.get_or_create(
                room_variant=variant, hotel=hotel
            )
            stock.quantity = stock_data["quantity"]
            stocks.append(stock)
        hotel_models.Stock.objects.bulk_update(stocks, ["quantity"])


class RoomVariantStocksDelete(BaseMutation):
    room_variant = graphene.Field(
        RoomVariant, description="Updated room variant."
    )

    class Arguments:
        variant_id = graphene.ID(
            required=True,
            description="ID of room variant for which stocks will be deleted.",
        )
        hotel_ids = graphene.List(
            graphene.NonNull(graphene.ID),
        )

    class Meta:
        description = "Delete stocks from room variant."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = StockError
        error_type_field = "stock_errors"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        variant = cls.get_node_or_error(
            info, data["variant_id"], only_type=RoomVariant
        )
        _, hotels_pks = resolve_global_ids_to_primary_keys(
            data["hotel_ids"], Hotel
        )
        hotel_models.Stock.objects.filter(
            room_variant=variant, hotel__pk__in=hotels_pks
        ).delete()

        variant = ChannelContext(node=variant, channel_slug=None)
        return cls(room_variant=variant)


class RoomTypeBulkDelete(ModelBulkDeleteMutation):
    class Arguments:
        ids = graphene.List(
            graphene.ID,
            required=True,
            description="List of room type IDs to delete.",
        )

    class Meta:
        description = "Deletes room types."
        model = models.RoomType
        permissions = (RoomTypePermissions.MANAGE_ROOM_TYPES_AND_ATTRIBUTES,)
        error_type_class = RoomError
        error_type_field = "room_errors"


class RoomImageBulkDelete(ModelBulkDeleteMutation):
    class Arguments:
        ids = graphene.List(
            graphene.ID,
            required=True,
            description="List of room image IDs to delete.",
        )

    class Meta:
        description = "Deletes room images."
        model = models.RoomImage
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = RoomError
        error_type_field = "room_errors"
