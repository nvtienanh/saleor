from django.db.models import Sum

from ...order import OrderStatus
from ...room import models
from ..channel import ChannelQsContext
from ..utils import get_database_id
from ..utils.filters import filter_by_period
from .filters import filter_rooms_by_stock_availability


def resolve_category_by_slug(slug):
    return models.Category.objects.filter(slug=slug).first()


def resolve_categories(_info, level=None, **_kwargs):
    qs = models.Category.objects.prefetch_related("children")
    if level is not None:
        qs = qs.filter(level=level)
    return qs.distinct()


def resolve_collection_by_id(info, id, channel_slug, requestor):
    return (
        models.Collection.objects.visible_to_user(requestor, channel_slug=channel_slug)
        .filter(id=id)
        .first()
    )


def resolve_collection_by_slug(info, slug, channel_slug, requestor):
    return (
        models.Collection.objects.visible_to_user(requestor, channel_slug)
        .filter(slug=slug)
        .first()
    )


def resolve_collections(info, channel_slug):
    user = info.context.user
    qs = models.Collection.objects.visible_to_user(user, channel_slug)

    return ChannelQsContext(qs=qs, channel_slug=channel_slug)


def resolve_digital_contents(_info):
    return models.DigitalContent.objects.all()


def resolve_room_by_id(info, id, channel_slug, requestor):
    return (
        models.Room.objects.visible_to_user(requestor, channel_slug=channel_slug)
        .filter(id=id)
        .first()
    )


def resolve_room_by_slug(info, room_slug, channel_slug, requestor):
    return (
        models.Room.objects.visible_to_user(requestor, channel_slug=channel_slug)
        .filter(slug=room_slug)
        .first()
    )


def resolve_rooms(
    info, requestor, stock_availability=None, channel_slug=None, **_kwargs
) -> ChannelQsContext:
    qs = models.Room.objects.visible_to_user(requestor, channel_slug)
    if stock_availability:
        qs = filter_rooms_by_stock_availability(qs, stock_availability)
    if not qs.user_has_access_to_all(requestor):
        qs = qs.annotate_visible_in_listings(channel_slug).exclude(
            visible_in_listings=False
        )
    return ChannelQsContext(qs=qs.distinct(), channel_slug=channel_slug)


def resolve_variant_by_id(info, id, channel_slug, requestor):
    visible_rooms = models.Room.objects.visible_to_user(
        requestor, channel_slug
    ).values_list("pk", flat=True)
    qs = models.RoomVariant.objects.filter(room__id__in=visible_rooms)
    return qs.filter(pk=id).first()


def resolve_room_types(_info, **_kwargs):
    return models.RoomType.objects.all()


def resolve_room_variant_by_sku(
    info, sku, channel_slug, requestor, requestor_has_access_to_all
):
    visible_rooms = models.Room.objects.visible_to_user(requestor, channel_slug)
    if not requestor_has_access_to_all:
        visible_rooms = visible_rooms.annotate_visible_in_listings(
            channel_slug
        ).exclude(visible_in_listings=False)

    return (
        models.RoomVariant.objects.filter(room__id__in=visible_rooms)
        .filter(sku=sku)
        .first()
    )


def resolve_room_variants(
    info, requestor_has_access_to_all, requestor, ids=None, channel_slug=None
) -> ChannelQsContext:
    visible_rooms = models.Room.objects.visible_to_user(requestor, channel_slug)
    if not requestor_has_access_to_all:
        visible_rooms = visible_rooms.annotate_visible_in_listings(
            channel_slug
        ).exclude(visible_in_listings=False)

    qs = models.RoomVariant.objects.filter(room__id__in=visible_rooms)
    if ids:
        db_ids = [get_database_id(info, node_id, "RoomVariant") for node_id in ids]
        qs = qs.filter(pk__in=db_ids)
    return ChannelQsContext(qs=qs, channel_slug=channel_slug)


def resolve_report_room_sales(period, channel_slug) -> ChannelQsContext:
    qs = models.RoomVariant.objects.all()

    # exclude draft and canceled orders
    exclude_status = [OrderStatus.DRAFT, OrderStatus.CANCELED]
    qs = qs.exclude(order_lines__order__status__in=exclude_status)

    # filter by period
    qs = filter_by_period(qs, period, "order_lines__order__created")

    qs = qs.annotate(quantity_ordered=Sum("order_lines__quantity"))
    qs = qs.filter(
        quantity_ordered__isnull=False, order_lines__order__channel__slug=channel_slug
    )
    qs = qs.order_by("-quantity_ordered")
    return ChannelQsContext(qs=qs, channel_slug=channel_slug)
