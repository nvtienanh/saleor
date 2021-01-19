import graphene

from ...core.permissions import OrderPermissions, RoomPermissions
from ...hotel import models
from ..core.fields import FilterInputConnectionField
from ..decorators import one_of_permissions_required, permission_required
from .filters import StockFilterInput, HotelFilterInput
from .mutations import (
    HotelCreate,
    HotelDelete,
    HotelShippingZoneAssign,
    HotelShippingZoneUnassign,
    HotelUpdate,
)
from .sorters import HotelSortingInput
from .types import Stock, Hotel


class HotelQueries(graphene.ObjectType):
    hotel = graphene.Field(
        Hotel,
        description="Look up a hotel by ID.",
        id=graphene.Argument(
            graphene.ID, description="ID of an hotel", required=True
        ),
    )
    hotels = FilterInputConnectionField(
        Hotel,
        description="List of hotels.",
        filter=HotelFilterInput(),
        sort_by=HotelSortingInput(),
    )

    @one_of_permissions_required(
        [RoomPermissions.MANAGE_ROOMS, OrderPermissions.MANAGE_ORDERS]
    )
    def resolve_hotel(self, info, **data):
        hotel_pk = data.get("id")
        hotel = graphene.Node.get_node_from_global_id(info, hotel_pk, Hotel)
        return hotel

    @one_of_permissions_required(
        [RoomPermissions.MANAGE_ROOMS, OrderPermissions.MANAGE_ORDERS]
    )
    def resolve_hotels(self, info, **_kwargs):
        return models.Hotel.objects.all()


class HotelMutations(graphene.ObjectType):
    create_hotel = HotelCreate.Field()
    update_hotel = HotelUpdate.Field()
    delete_hotel = HotelDelete.Field()
    assign_hotel_shipping_zone = HotelShippingZoneAssign.Field()
    unassign_hotel_shipping_zone = HotelShippingZoneUnassign.Field()


class StockQueries(graphene.ObjectType):
    stock = graphene.Field(
        Stock,
        description="Look up a stock by ID",
        id=graphene.ID(required=True, description="ID of an hotel"),
    )
    stocks = FilterInputConnectionField(
        Stock, description="List of stocks.", filter=StockFilterInput()
    )

    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_stock(self, info, **kwargs):
        stock_id = kwargs.get("id")
        stock = graphene.Node.get_node_from_global_id(info, stock_id, Stock)
        return stock

    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_stocks(self, info, **_kwargs):
        return models.Stock.objects.all()
