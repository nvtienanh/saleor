from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Iterable, List, Set, Union

from django.conf import settings

if TYPE_CHECKING:
    # flake8: noqa
    from .models import Sale, SaleChannelListing, Voucher


class DiscountValueType:
    FIXED = "fixed"
    PERCENTAGE = "percentage"

    CHOICES = [
        (FIXED, "fixed"),
        (PERCENTAGE, "%"),
    ]


class VoucherType:
    SHIPPING = "shipping"
    ENTIRE_ORDER = "entire_order"
    SPECIFIC_ROOM = "specific_room"

    CHOICES = [
        (ENTIRE_ORDER, "Entire order"),
        (SHIPPING, "Shipping"),
        (SPECIFIC_ROOM, "Specific rooms, collections and categories"),
    ]


@dataclass
class DiscountInfo:
    sale: Union["Sale", "Voucher"]
    channel_listings: Dict[str, "SaleChannelListing"]
    room_ids: Union[List[int], Set[int]]
    category_ids: Union[List[int], Set[int]]
    collection_ids: Union[List[int], Set[int]]
