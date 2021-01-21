import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..room.models import (
        Collection,
        Room,
        RoomVariant,
        RoomVariantChannelListing,
    )
    from .models import CheckoutLine

logger = logging.getLogger(__name__)


class AddressType:
    BILLING = "billing"
    SHIPPING = "shipping"

    CHOICES = [
        (BILLING, "Billing"),
        (SHIPPING, "Shipping"),
    ]


@dataclass
class CheckoutLineInfo:
    line: "CheckoutLine"
    variant: "RoomVariant"
    channel_listing: "RoomVariantChannelListing"
    room: "Room"
    collections: List["Collection"]
