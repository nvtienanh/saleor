from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple, Union

import opentracing
from django.conf import settings
from prices import MoneyRange, TaxedMoney, TaxedMoneyRange

from ...channel.models import Channel
from ...core.utils import to_local_currency
from ...discount import DiscountInfo
from ...discount.utils import calculate_discounted_price
from ...plugins.manager import get_plugins_manager
from ...room.models import (
    Collection,
    Room,
    RoomChannelListing,
    RoomVariant,
    RoomVariantChannelListing,
)

if TYPE_CHECKING:
    # flake8: noqa
    from ...plugins.manager import PluginsManager


@dataclass
class RoomAvailability:
    on_sale: bool
    price_range: Optional[TaxedMoneyRange]
    price_range_undiscounted: Optional[TaxedMoneyRange]
    discount: Optional[TaxedMoney]
    price_range_local_currency: Optional[TaxedMoneyRange]
    discount_local_currency: Optional[TaxedMoneyRange]


@dataclass
class VariantAvailability:
    on_sale: bool
    price: TaxedMoney
    price_undiscounted: TaxedMoney
    discount: Optional[TaxedMoney]
    price_local_currency: Optional[TaxedMoney]
    discount_local_currency: Optional[TaxedMoney]


def _get_total_discount_from_range(
    undiscounted: TaxedMoneyRange, discounted: TaxedMoneyRange
) -> Optional[TaxedMoney]:
    """Calculate the discount amount between two TaxedMoneyRange.

    Subtract two prices and return their total discount, if any.
    Otherwise, it returns None.
    """
    return _get_total_discount(undiscounted.start, discounted.start)


def _get_total_discount(
    undiscounted: TaxedMoney, discounted: TaxedMoney
) -> Optional[TaxedMoney]:
    """Calculate the discount amount between two TaxedMoney.

    Subtract two prices and return their total discount, if any.
    Otherwise, it returns None.
    """
    if undiscounted > discounted:
        return undiscounted - discounted
    return None


def _get_room_price_range(
    discounted: Union[MoneyRange, TaxedMoneyRange],
    undiscounted: Union[MoneyRange, TaxedMoneyRange],
    local_currency: Optional[str] = None,
) -> Tuple[TaxedMoneyRange, TaxedMoney]:
    price_range_local = None
    discount_local_currency = None

    if local_currency:
        price_range_local = to_local_currency(discounted, local_currency)
        undiscounted_local = to_local_currency(undiscounted, local_currency)
        if undiscounted_local and undiscounted_local.start > price_range_local.start:
            discount_local_currency = undiscounted_local.start - price_range_local.start

    return price_range_local, discount_local_currency


def get_variant_price(
    *,
    variant: RoomVariant,
    variant_channel_listing: RoomVariantChannelListing,
    room: Room,
    collections: Iterable[Collection],
    discounts: Iterable[DiscountInfo],
    channel: Channel
):
    return calculate_discounted_price(
        room=room,
        price=variant_channel_listing.price,
        collections=collections,
        discounts=discounts,
        channel=channel,
    )


def get_room_price_range(
    *,
    room: Room,
    variants: Iterable[RoomVariant],
    variants_channel_listing: List[RoomVariantChannelListing],
    collections: Iterable[Collection],
    discounts: Iterable[DiscountInfo],
    channel: Channel,
) -> Optional[MoneyRange]:
    with opentracing.global_tracer().start_active_span("get_room_price_range"):
        if variants:
            variants_channel_listing_dict = {
                channel_listing.variant_id: channel_listing
                for channel_listing in variants_channel_listing
                if channel_listing
            }
            prices = []
            for variant in variants:
                variant_channel_listing = variants_channel_listing_dict.get(variant.id)
                if variant_channel_listing:
                    price = get_variant_price(
                        variant=variant,
                        variant_channel_listing=variant_channel_listing,
                        room=room,
                        collections=collections,
                        discounts=discounts,
                        channel=channel,
                    )
                    prices.append(price)
            if prices:
                return MoneyRange(min(prices), max(prices))

        return None


def get_room_availability(
    *,
    room: Room,
    room_channel_listing: Optional[RoomChannelListing],
    variants: Iterable[RoomVariant],
    variants_channel_listing: List[RoomVariantChannelListing],
    collections: Iterable[Collection],
    discounts: Iterable[DiscountInfo],
    channel: Channel,
    country: Optional[str] = None,
    local_currency: Optional[str] = None,
    plugins: Optional["PluginsManager"] = None,
) -> RoomAvailability:
    with opentracing.global_tracer().start_active_span("get_room_availability"):
        if not plugins:
            plugins = get_plugins_manager()
        discounted = None
        discounted_net_range = get_room_price_range(
            room=room,
            variants=variants,
            variants_channel_listing=variants_channel_listing,
            collections=collections,
            discounts=discounts,
            channel=channel,
        )
        if discounted_net_range is not None:
            discounted = TaxedMoneyRange(
                start=plugins.apply_taxes_to_room(
                    room, discounted_net_range.start, country
                ),
                stop=plugins.apply_taxes_to_room(
                    room, discounted_net_range.stop, country
                ),
            )

        undiscounted = None
        undiscounted_net_range = get_room_price_range(
            room=room,
            variants=variants,
            variants_channel_listing=variants_channel_listing,
            collections=collections,
            discounts=[],
            channel=channel,
        )
        if undiscounted_net_range is not None:
            undiscounted = TaxedMoneyRange(
                start=plugins.apply_taxes_to_room(
                    room, undiscounted_net_range.start, country
                ),
                stop=plugins.apply_taxes_to_room(
                    room, undiscounted_net_range.stop, country
                ),
            )

        discount = None
        price_range_local = None
        discount_local_currency = None
        if undiscounted_net_range is not None and discounted_net_range is not None:
            discount = _get_total_discount_from_range(undiscounted, discounted)
            price_range_local, discount_local_currency = _get_room_price_range(
                discounted, undiscounted, local_currency
            )

        is_visible = (
            room_channel_listing is not None and room_channel_listing.is_visible
        )
        is_on_sale = is_visible and discount is not None

        return RoomAvailability(
            on_sale=is_on_sale,
            price_range=discounted,
            price_range_undiscounted=undiscounted,
            discount=discount,
            price_range_local_currency=price_range_local,
            discount_local_currency=discount_local_currency,
        )


def get_variant_availability(
    variant: RoomVariant,
    variant_channel_listing: RoomVariantChannelListing,
    room: Room,
    room_channel_listing: Optional[RoomChannelListing],
    collections: Iterable[Collection],
    discounts: Iterable[DiscountInfo],
    channel: Channel,
    country: Optional[str] = None,
    local_currency: Optional[str] = None,
    plugins: Optional["PluginsManager"] = None,
) -> VariantAvailability:
    with opentracing.global_tracer().start_active_span("get_variant_availability"):
        if not plugins:
            plugins = get_plugins_manager()
        discounted = plugins.apply_taxes_to_room(
            room,
            get_variant_price(
                variant=variant,
                variant_channel_listing=variant_channel_listing,
                room=room,
                collections=collections,
                discounts=discounts,
                channel=channel,
            ),
            country,
        )
        undiscounted = plugins.apply_taxes_to_room(
            room,
            get_variant_price(
                variant=variant,
                variant_channel_listing=variant_channel_listing,
                room=room,
                collections=collections,
                discounts=[],
                channel=channel,
            ),
            country,
        )

        discount = _get_total_discount(undiscounted, discounted)

        if country is None:
            country = settings.DEFAULT_COUNTRY

        if local_currency:
            price_local_currency = to_local_currency(discounted, local_currency)
            discount_local_currency = to_local_currency(discount, local_currency)
        else:
            price_local_currency = None
            discount_local_currency = None

        is_visible = (
            room_channel_listing is not None and room_channel_listing.is_visible
        )
        is_on_sale = is_visible and discount is not None

        return VariantAvailability(
            on_sale=is_on_sale,
            price=discounted,
            price_undiscounted=undiscounted,
            discount=discount,
            price_local_currency=price_local_currency,
            discount_local_currency=discount_local_currency,
        )
