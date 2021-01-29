import graphene
from django.db.models import Sum, Min
from django.db.models.functions import Coalesce

from ...core.permissions import OrderPermissions, RoomPermissions
from ...hotel import models
from ...room.models import Room
from ..account.enums import CountryCodeEnum
from ..channel import ChannelContext
from ..core.connection import CountableDjangoObjectType
from ..core.fields import FilterInputConnectionField, PrefetchingConnectionField
from ..core.scalars import Decimal
from ..core.types import Money, Image
from ..decorators import one_of_permissions_required
from ..meta.types import ObjectWithMetadata

class HotelAddressInput(graphene.InputObjectType):
    street_address_1 = graphene.String(description="Address.", required=True)
    street_address_2 = graphene.String(description="Address.")
    city = graphene.String(description="City.", required=True)
    city_area = graphene.String(description="District.")
    postal_code = graphene.String(description="Postal code.")
    country = CountryCodeEnum(description="Country.", required=True)
    country_area = graphene.String(description="State or province.")
    phone = graphene.String(description="Phone number.")


class HotelInput(graphene.InputObjectType):
    slug = graphene.String(description="Hotel slug.")
    company_name = graphene.String(description="Company name.")
    email = graphene.String(description="The email address of the hotel.")
    latitude = graphene.Float(description="The latitude value of hotel on map.")
    longitude = graphene.Float(description="The longitude value of hotel on map.")
    star_rating = graphene.Int(description="The rating of the hotel.")
    price_per_hour = Decimal(description="Hotel min hourly price.")
    price_per_night = Decimal(description="Hotel min nightly price.")
    distance = graphene.String(description="The rating of the hotel.")
    payment = graphene.String(description="The rating of the hotel.")
    image_url = graphene.String(description="The rating of the hotel.")
    detail = graphene.String(description="The rating of the hotel.")
    

class HotelCreateInput(HotelInput):
    name = graphene.String(description="Hotel name.", required=True)
    address = HotelAddressInput(
        description="Address of the hotel.", required=True
    )
    """TODO remove `shipping` fields
    shipping_zones = graphene.List(
        graphene.ID, description="Shipping zones supported by the hotel."
    )
    """


class HotelUpdateInput(HotelInput):
    name = graphene.String(description="Hotel name.", required=False)
    address = HotelAddressInput(
        description="Address of the hotel.", required=False
    )


class Hotel(CountableDjangoObjectType):
    cover_image = graphene.Field(Image, size=graphene.Int(description="Size of the cover image."))
    rooms = PrefetchingConnectionField(
        "vanphong.graphql.room.types.Room", description="List of hotel's room."
    )
    minimal_room_base_price = graphene.Field(Money, description="The minimal hotel price.")
    minimal_room_base_hourly_price = graphene.Field(Money, description="The minimal hotel hourly price.")
    
    class Meta:
        description = "Represents hotel."
        model = models.Hotel
        interfaces = [graphene.relay.Node, ObjectWithMetadata]
        only_fields = [
            "id",
            "name",
            "slug",
            "company_name",
            # "shipping_zones",
            "address",
            "email",
            "star_rating",
            "latitude",
            "longitude",
            "distance",
            "payment",
            "image_url",
            "detail",
        ]

    """TODO remove `shipping` fields
    @staticmethod
    def resolve_shipping_zones(root, *_args, **_kwargs):
        instances = root.shipping_zones.all()
        shipping_zones = [
            ChannelContext(node=shipping_zone, channel_slug=None)
            for shipping_zone in instances
        ]
        return shipping_zones
    """

    @staticmethod
    def resolve_minimal_room_base_price(root: models.Hotel, _info):
        result = (
            Room.objects
                .filter(hotel__id=root.id) #.all().select_related("room_bookings")
                .aggregate(Min('base_price_amount'))
        )
        if result['base_price_amount__min'] is None:
            return Money(amount=0, currency=root.currency)
        else:
            return Money(amount=result['base_price_amount__min'], currency=root.currency)

    @staticmethod
    def resolve_minimal_room_base_hourly_price(root: models.Hotel, _info):
        result = (
            Room.objects
                .filter(hotel__id=root.id) #.all().select_related("room_bookings")
                .aggregate(Min('base_hourly_price_amount'))
        )
        if result['base_hourly_price_amount__min'] is None:
            return Money(amount=0, currency=root.currency)
        else:
            return Money(amount=result['base_hourly_price_amount__min'], currency=root.currency)

    @staticmethod
    def resolve_cover_image(root: models.Hotel, info, size=None, **_kwargs):
        if root.cover_image:
            return Image.get_adjusted(
                image=root.cover_image,
                alt=None,
                size=size,
                rendition_key_set="hotel_cover_images",
                info=info,
            )


class Stock(CountableDjangoObjectType):
    quantity = graphene.Int(
        required=True,
        description="Quantity of a room in the hotel's possession, "
        "including the allocated stock that is waiting for shipment.",
    )
    quantity_allocated = graphene.Int(
        required=True, description="Quantity allocated for orders"
    )

    class Meta:
        description = "Represents stock."
        model = models.Stock
        interfaces = [graphene.relay.Node]
        only_fields = ["hotel", "room_variant", "quantity", "quantity_allocated"]

    @staticmethod
    @one_of_permissions_required(
        [RoomPermissions.MANAGE_ROOMS, OrderPermissions.MANAGE_ORDERS]
    )
    def resolve_quantity(root, *_args):
        return root.quantity

    @staticmethod
    @one_of_permissions_required(
        [RoomPermissions.MANAGE_ROOMS, OrderPermissions.MANAGE_ORDERS]
    )
    def resolve_quantity_allocated(root, *_args):
        return root.allocations.aggregate(
            quantity_allocated=Coalesce(Sum("quantity_allocated"), 0)
        )["quantity_allocated"]

    @staticmethod
    def resolve_room_variant(root, *_args):
        return ChannelContext(node=root.room_variant, channel_slug=None)


class Allocation(CountableDjangoObjectType):
    quantity = graphene.Int(required=True, description="Quantity allocated for orders.")
    hotel = graphene.Field(
        Hotel, required=True, description="The hotel were items were allocated."
    )

    class Meta:
        description = "Represents allocation."
        model = models.Allocation
        interfaces = [graphene.relay.Node]
        only_fields = ["id"]

    @staticmethod
    @one_of_permissions_required(
        [RoomPermissions.MANAGE_ROOMS, OrderPermissions.MANAGE_ORDERS]
    )
    def resolve_hotel(root, *_args):
        return root.stock.hotel

    @staticmethod
    @one_of_permissions_required(
        [RoomPermissions.MANAGE_ROOMS, OrderPermissions.MANAGE_ORDERS]
    )
    def resolve_quantity(root, *_args):
        return root.quantity_allocated
