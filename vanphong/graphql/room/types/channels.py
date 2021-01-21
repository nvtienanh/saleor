from dataclasses import asdict

import graphene

from vanphong.graphql.room.dataloaders.rooms import RoomByIdLoader

from ....core.permissions import RoomPermissions
from ....graphql.core.types import Money, MoneyRange
from ....room import models
from ....room.utils.availability import get_room_availability
from ....room.utils.costs import (
    get_margin_for_variant_channel_listing,
    get_room_costs_data,
)
from ...channel.dataloaders import ChannelByIdLoader
from ...core.connection import CountableDjangoObjectType
from ...decorators import permission_required
from ...discount.dataloaders import DiscountsByDateTimeLoader
from ..dataloaders import (
    CollectionsByRoomIdLoader,
    RoomVariantsByRoomIdLoader,
    VariantChannelListingByVariantIdAndChannelSlugLoader,
    VariantsChannelListingByRoomIdAndChanneSlugLoader,
)


class Margin(graphene.ObjectType):
    start = graphene.Int()
    stop = graphene.Int()


class RoomChannelListing(CountableDjangoObjectType):
    discounted_price = graphene.Field(
        Money, description="The price of the cheapest variant (including discounts)."
    )
    purchase_cost = graphene.Field(MoneyRange, description="Purchase cost of room.")
    margin = graphene.Field(Margin, description="Range of margin percentage value.")
    is_available_for_purchase = graphene.Boolean(
        description="Whether the room is available for purchase."
    )
    pricing = graphene.Field(
        "vanphong.graphql.room.types.rooms.RoomPricingInfo",
        description=(
            "Lists the storefront room's pricing, the current price and discounts, "
            "only meant for displaying."
        ),
    )

    class Meta:
        description = "Represents room channel listing."
        model = models.RoomChannelListing
        interfaces = [graphene.relay.Node]
        only_fields = [
            "id",
            "channel",
            "is_published",
            "publication_date",
            "visible_in_listings",
            "available_for_purchase",
        ]

    @staticmethod
    def resolve_channel(root: models.RoomChannelListing, info, **_kwargs):
        return ChannelByIdLoader(info.context).load(root.channel_id)

    @staticmethod
    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_purchase_cost(root: models.RoomChannelListing, info, *_kwargs):
        channel = ChannelByIdLoader(info.context).load(root.channel_id)

        def calculate_margin_with_variants(variants):
            def calculate_margin_with_channel(channel):
                def calculate_margin_with_channel_listings(variant_channel_listings):
                    variant_channel_listings = list(
                        filter(None, variant_channel_listings)
                    )
                    if not variant_channel_listings:
                        return None

                    has_variants = True if len(variant_ids_channel_slug) > 0 else False
                    purchase_cost, _margin = get_room_costs_data(
                        variant_channel_listings, has_variants, root.currency
                    )
                    return purchase_cost

                variant_ids_channel_slug = [
                    (variant.id, channel.slug) for variant in variants
                ]
                return (
                    VariantChannelListingByVariantIdAndChannelSlugLoader(info.context)
                    .load_many(variant_ids_channel_slug)
                    .then(calculate_margin_with_channel_listings)
                )

            return channel.then(calculate_margin_with_channel)

        return (
            RoomVariantsByRoomIdLoader(info.context)
            .load(root.room_id)
            .then(calculate_margin_with_variants)
        )

    @staticmethod
    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_margin(root: models.RoomChannelListing, info, *_kwargs):
        channel = ChannelByIdLoader(info.context).load(root.channel_id)

        def calculate_margin_with_variants(variants):
            def calculate_margin_with_channel(channel):
                def calculate_margin_with_channel_listings(variant_channel_listings):
                    variant_channel_listings = list(
                        filter(None, variant_channel_listings)
                    )
                    if not variant_channel_listings:
                        return None

                    has_variants = True if len(variant_ids_channel_slug) > 0 else False
                    _purchase_cost, margin = get_room_costs_data(
                        variant_channel_listings, has_variants, root.currency
                    )
                    return Margin(margin[0], margin[1])

                variant_ids_channel_slug = [
                    (variant.id, channel.slug) for variant in variants
                ]
                return (
                    VariantChannelListingByVariantIdAndChannelSlugLoader(info.context)
                    .load_many(variant_ids_channel_slug)
                    .then(calculate_margin_with_channel_listings)
                )

            return channel.then(calculate_margin_with_channel)

        return (
            RoomVariantsByRoomIdLoader(info.context)
            .load(root.room_id)
            .then(calculate_margin_with_variants)
        )

    @staticmethod
    def resolve_is_available_for_purchase(root: models.RoomChannelListing, _info):
        return root.is_available_for_purchase()

    @staticmethod
    def resolve_pricing(root: models.RoomChannelListing, info):
        context = info.context

        def calculate_pricing_info(discounts):
            def calculate_pricing_with_channel(channel):
                def calculate_pricing_with_room(room):
                    def calculate_pricing_with_variants(variants):
                        def calculate_pricing_with_variants_channel_listings(
                            variants_channel_listing,
                        ):
                            def calculate_pricing_with_collections(collections):
                                if not variants_channel_listing:
                                    return None
                                availability = get_room_availability(
                                    room=room,
                                    room_channel_listing=root,
                                    variants=variants,
                                    variants_channel_listing=variants_channel_listing,
                                    collections=collections,
                                    discounts=discounts,
                                    channel=channel,
                                    country=context.country,
                                    local_currency=context.currency,
                                    plugins=context.plugins,
                                )
                                from .rooms import RoomPricingInfo

                                return RoomPricingInfo(**asdict(availability))

                            return (
                                CollectionsByRoomIdLoader(context)
                                .load(root.room_id)
                                .then(calculate_pricing_with_collections)
                            )

                        return (
                            VariantsChannelListingByRoomIdAndChanneSlugLoader(
                                context
                            )
                            .load((root.room_id, channel.slug))
                            .then(calculate_pricing_with_variants_channel_listings)
                        )

                    return (
                        RoomVariantsByRoomIdLoader(context)
                        .load(root.room_id)
                        .then(calculate_pricing_with_variants)
                    )

                return (
                    RoomByIdLoader(context)
                    .load(root.room_id)
                    .then(calculate_pricing_with_room)
                )

            return (
                ChannelByIdLoader(context)
                .load(root.channel_id)
                .then(calculate_pricing_with_channel)
            )

        return (
            DiscountsByDateTimeLoader(context)
            .load(info.context.request_time)
            .then(calculate_pricing_info)
        )


class RoomVariantChannelListing(CountableDjangoObjectType):
    cost_price = graphene.Field(Money, description="Cost price of the variant.")
    margin = graphene.Int(description="Gross margin percentage value.")

    class Meta:
        description = "Represents room varaint channel listing."
        model = models.RoomVariantChannelListing
        interfaces = [graphene.relay.Node]
        only_fields = ["id", "channel", "price", "cost_price"]

    @staticmethod
    def resolve_channel(root: models.RoomVariantChannelListing, info, **_kwargs):
        return ChannelByIdLoader(info.context).load(root.channel_id)

    @staticmethod
    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_margin(root: models.RoomVariantChannelListing, *_args):
        return get_margin_for_variant_channel_listing(root)


class CollectionChannelListing(CountableDjangoObjectType):
    class Meta:
        description = "Represents collection channel listing."
        model = models.CollectionChannelListing
        interfaces = [graphene.relay.Node]
        only_fields = ["id", "channel", "is_published", "publication_date"]

    @staticmethod
    def resolve_channel(root: models.RoomChannelListing, info, **_kwargs):
        return ChannelByIdLoader(info.context).load(root.channel_id)
