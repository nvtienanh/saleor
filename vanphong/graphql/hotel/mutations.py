import graphene
from django.core.exceptions import ValidationError

from ...core.permissions import RoomPermissions
from ...hotel import models
from ...hotel.error_codes import HotelErrorCode
from ...hotel.validation import validate_hotel_count  # type: ignore
from ..account.i18n import I18nMixin
from ..core.mutations import ModelDeleteMutation, ModelMutation
from ..core.types.common import HotelError
from ..core.utils import (
    validate_required_string_field,
    validate_slug_and_generate_if_needed,
)
"""TODO remove `shipping` fields
from ..shipping.types import ShippingZone
"""
from .types import Hotel, HotelCreateInput, HotelUpdateInput

ADDRESS_FIELDS = [
    "street_address_1",
    "street_address_2",
    "city",
    "city_area",
    "postal_code",
    "country",
    "country_area",
    "phone",
]


class HotelMixin:
    @classmethod
    def clean_input(cls, info, instance, data, input_cls=None):
        cleaned_input = super().clean_input(info, instance, data)
        try:
            cleaned_input = validate_slug_and_generate_if_needed(
                instance, "name", cleaned_input
            )
        except ValidationError as error:
            error.code = HotelErrorCode.REQUIRED.value
            raise ValidationError({"slug": error})

        if "name" in cleaned_input:
            try:
                cleaned_input = validate_required_string_field(cleaned_input, "name")
            except ValidationError as error:
                error.code = HotelErrorCode.REQUIRED.value
                raise ValidationError({"name": error})

        """TODO remove `shipping` fields
        shipping_zones = cleaned_input.get("shipping_zones", [])
        if not validate_hotel_count(shipping_zones, instance):
            msg = "Shipping zone can be assigned only to one hotel."
            raise ValidationError(
                {"shipping_zones": msg}, code=HotelErrorCode.INVALID
            )
        """
        return cleaned_input

    @classmethod
    def construct_instance(cls, instance, cleaned_data):
        cleaned_data["address"] = cls.prepare_address(cleaned_data, instance)
        return super().construct_instance(instance, cleaned_data)


class HotelCreate(HotelMixin, ModelMutation, I18nMixin):
    class Arguments:
        input = HotelCreateInput(
            required=True, description="Fields required to create hotel."
        )

    class Meta:
        description = "Creates new hotel."
        model = models.Hotel
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = HotelError
        error_type_field = "hotel_errors"

    @classmethod
    def prepare_address(cls, cleaned_data, *args):
        address_form = cls.validate_address_form(cleaned_data["address"])
        return address_form.save()


"""TODO remove `shipping` fields
class HotelShippingZoneAssign(HotelMixin, ModelMutation, I18nMixin):
    class Meta:
        model = models.Hotel
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        description = "Add shipping zone to given hotel."
        error_type_class = HotelError
        error_type_field = "hotel_errors"

    class Arguments:
        id = graphene.ID(description="ID of a hotel to update.", required=True)
        shipping_zone_ids = graphene.List(
            graphene.NonNull(graphene.ID),
            required=True,
            description="List of shipping zone IDs.",
        )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        hotel = cls.get_node_or_error(info, data.get("id"), only_type=Hotel)
        shipping_zones = cls.get_nodes_or_error(
            data.get("shipping_zone_ids"), "shipping_zone_id", only_type=ShippingZone
        )
        hotel.shipping_zones.add(*shipping_zones)
        return HotelShippingZoneAssign(hotel=hotel)


class HotelShippingZoneUnassign(HotelMixin, ModelMutation, I18nMixin):
    class Meta:
        model = models.Hotel
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        description = "Remove shipping zone from given hotel."
        error_type_class = HotelError
        error_type_field = "hotel_errors"

    class Arguments:
        id = graphene.ID(description="ID of a hotel to update.", required=True)
        shipping_zone_ids = graphene.List(
            graphene.NonNull(graphene.ID),
            required=True,
            description="List of shipping zone IDs.",
        )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        hotel = cls.get_node_or_error(info, data.get("id"), only_type=Hotel)
        shipping_zones = cls.get_nodes_or_error(
            data.get("shipping_zone_ids"), "shipping_zone_id", only_type=ShippingZone
        )
        hotel.shipping_zones.remove(*shipping_zones)
        return HotelShippingZoneAssign(hotel=hotel)
"""


class HotelUpdate(HotelMixin, ModelMutation, I18nMixin):
    class Meta:
        model = models.Hotel
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        description = "Updates given hotel."
        error_type_class = HotelError
        error_type_field = "hotel_errors"

    class Arguments:
        id = graphene.ID(description="ID of a hotel to update.", required=True)
        input = HotelUpdateInput(
            required=True, description="Fields required to update hotel."
        )

    @classmethod
    def prepare_address(cls, cleaned_data, instance):
        address_data = cleaned_data.get("address")
        address = instance.address
        if address_data is None:
            return address
        address_form = cls.validate_address_form(address_data, instance=address)
        return address_form.save()


class HotelDelete(ModelDeleteMutation):
    class Meta:
        model = models.Hotel
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        description = "Deletes selected hotel."
        error_type_class = HotelError
        error_type_field = "hotel_errors"

    class Arguments:
        id = graphene.ID(description="ID of a hotel to delete.", required=True)
