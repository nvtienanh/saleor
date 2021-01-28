from typing import TYPE_CHECKING, Dict, Iterable, List, Union

from django.db import transaction

from ...core.taxes import TaxedMoney, zero_taxed_money
from ..models import Room, RoomChannelListing
from ..tasks import update_rooms_discounted_prices_task

if TYPE_CHECKING:
    # flake8: noqa
    from datetime import date, datetime

    from django.db.models.query import QuerySet

    from ...order.models import Order, OrderLine
    from ..models import Category, Room, RoomVariant


def calculate_revenue_for_variant(
    variant: "RoomVariant",
    start_date: Union["date", "datetime"],
    order_lines: Iterable["OrderLine"],
    orders_dict: Dict[int, "Order"],
    currency_code: str,
) -> TaxedMoney:
    """Calculate total revenue generated by a room variant."""
    revenue = zero_taxed_money(currency_code)
    for order_line in order_lines:
        order = orders_dict[order_line.order_id]
        if order.created >= start_date:
            revenue += order_line.total_price
    return revenue


@transaction.atomic
def delete_categories(categories_ids: List[str]):
    """Delete categories and perform all necessary actions.

    Set rooms of deleted categories as unpublished, delete categories
    and update rooms minimal variant prices.
    """
    from ..models import Category, Room

    categories = Category.objects.select_for_update().filter(pk__in=categories_ids)
    categories.prefetch_related("rooms")

    rooms = Room.objects.none()
    for category in categories:
        rooms = rooms | collect_categories_tree_rooms(category)

    RoomChannelListing.objects.filter(room__in=rooms).update(
        is_published=False, publication_date=None
    )
    room_ids = list(rooms.values_list("id", flat=True))
    categories.delete()
    update_rooms_discounted_prices_task.delay(room_ids=room_ids)


def collect_categories_tree_rooms(category: "Category") -> "QuerySet[Room]":
    """Collect rooms from all levels in category tree."""
    rooms = category.rooms.all()
    descendants = category.get_descendants()
    for descendant in descendants:
        rooms = rooms | descendant.rooms.all()
    return rooms


def get_rooms_ids_without_variants(rooms_list: "List[Room]") -> "List[str]":
    """Return list of room's ids without variants."""
    rooms_ids = [room.id for room in rooms_list]
    rooms_ids_without_variants = Room.objects.filter(
        id__in=rooms_ids, variants__isnull=True
    ).values_list("id", flat=True)
    return list(rooms_ids_without_variants)