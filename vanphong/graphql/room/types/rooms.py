from dataclasses import asdict
from typing import Optional

import graphene
from django.conf import settings
from graphene import relay
from graphene_federation import key
from graphql.error import GraphQLError

from ....account.utils import requestor_is_staff_member_or_app
from ....attribute import models as attribute_models
from ....core.permissions import OrderPermissions, RoomPermissions
from ....core.weight import convert_weight_to_default_weight_unit
from ....room import models
from ....room.templatetags.room_images import (
    get_room_image_thumbnail,
    get_thumbnail,
)
from ....room.utils import calculate_revenue_for_variant
from ....room.utils.availability import (
    get_room_availability,
    get_variant_availability,
)
from ....room.utils.variants import get_variant_selection_attributes
from ....hotel.availability import is_room_in_stock
from ...account.enums import CountryCodeEnum
from ...attribute.filters import AttributeFilterInput
from ...attribute.resolvers import resolve_attributes
from ...attribute.types import Attribute, SelectedAttribute
from ...channel import ChannelContext, ChannelQsContext
from ...channel.dataloaders import ChannelBySlugLoader
from ...channel.types import ChannelContextType, ChannelContextTypeWithMetadata
from ...channel.utils import get_default_channel_slug_or_graphql_error
from ...core.connection import CountableDjangoObjectType
from ...core.enums import ReportingPeriod, TaxRateType
from ...core.fields import (
    ChannelContextFilterConnectionField,
    FilterInputConnectionField,
    PrefetchingConnectionField,
)
from ...core.types import Image, Money, TaxedMoney, TaxedMoneyRange, TaxType
from ...decorators import (
    one_of_permissions_required,
    permission_required,
    staff_member_or_app_required,
)
from ...discount.dataloaders import DiscountsByDateTimeLoader
from ...meta.types import ObjectWithMetadata
from ...order.dataloaders import (
    OrderByIdLoader,
    OrderLinesByVariantIdAndChannelIdLoader,
)
from ...translations.fields import TranslationField
from ...translations.types import (
    CategoryTranslation,
    CollectionTranslation,
    RoomTranslation,
    RoomVariantTranslation,
)
from ...utils import get_database_id, get_user_or_app_from_context
from ...utils.filters import reporting_period_to_date
from ...hotel.dataloaders import (
    AvailableQuantityByRoomVariantIdAndCountryCodeLoader,
)
from ...hotel.types import Stock
from ..dataloaders import (
    CategoryByIdLoader,
    CollectionChannelListingByCollectionIdAndChannelSlugLoader,
    CollectionChannelListingByCollectionIdLoader,
    CollectionsByRoomIdLoader,
    ImagesByRoomIdLoader,
    ImagesByRoomVariantIdLoader,
    RoomAttributesByRoomTypeIdLoader,
    RoomByIdLoader,
    RoomChannelListingByRoomIdAndChannelSlugLoader,
    RoomChannelListingByRoomIdLoader,
    RoomTypeByIdLoader,
    RoomVariantByIdLoader,
    RoomVariantsByRoomIdLoader,
    SelectedAttributesByRoomIdLoader,
    SelectedAttributesByRoomVariantIdLoader,
    VariantAttributesByRoomTypeIdLoader,
    VariantChannelListingByVariantIdAndChannelSlugLoader,
    VariantChannelListingByVariantIdLoader,
    VariantsChannelListingByRoomIdAndChanneSlugLoader,
)
from ..enums import VariantAttributeScope
from ..filters import RoomFilterInput
from ..sorters import RoomOrder
from .channels import (
    CollectionChannelListing,
    RoomChannelListing,
    RoomVariantChannelListing,
)
from .digital_contents import DigitalContent


class Margin(graphene.ObjectType):
    start = graphene.Int()
    stop = graphene.Int()


class BasePricingInfo(graphene.ObjectType):
    on_sale = graphene.Boolean(description="Whether it is in sale or not.")
    discount = graphene.Field(
        TaxedMoney, description="The discount amount if in sale (null otherwise)."
    )
    discount_local_currency = graphene.Field(
        TaxedMoney, description="The discount amount in the local currency."
    )


class VariantPricingInfo(BasePricingInfo):
    discount_local_currency = graphene.Field(
        TaxedMoney, description="The discount amount in the local currency."
    )
    price = graphene.Field(
        TaxedMoney, description="The price, with any discount subtracted."
    )
    price_undiscounted = graphene.Field(
        TaxedMoney, description="The price without any discount."
    )
    price_local_currency = graphene.Field(
        TaxedMoney, description="The discounted price in the local currency."
    )

    class Meta:
        description = "Represents availability of a variant in the storefront."


class RoomPricingInfo(BasePricingInfo):
    price_range = graphene.Field(
        TaxedMoneyRange,
        description="The discounted price range of the room variants.",
    )
    price_range_undiscounted = graphene.Field(
        TaxedMoneyRange,
        description="The undiscounted price range of the room variants.",
    )
    price_range_local_currency = graphene.Field(
        TaxedMoneyRange,
        description=(
            "The discounted price range of the room variants "
            "in the local currency."
        ),
    )

    class Meta:
        description = "Represents availability of a room in the storefront."


@key(fields="id")
class RoomVariant(ChannelContextTypeWithMetadata, CountableDjangoObjectType):
    channel_listings = graphene.List(
        graphene.NonNull(RoomVariantChannelListing),
        description="List of price information in channels for the room.",
    )
    pricing = graphene.Field(
        VariantPricingInfo,
        description=(
            "Lists the storefront variant's pricing, the current price and discounts, "
            "only meant for displaying."
        ),
    )
    attributes = graphene.List(
        graphene.NonNull(SelectedAttribute),
        required=True,
        description="List of attributes assigned to this variant.",
        variant_selection=graphene.Argument(
            VariantAttributeScope,
            description="Define scope of returned attributes.",
        ),
    )
    cost_price = graphene.Field(Money, description="Cost price of the variant.")
    margin = graphene.Int(description="Gross margin percentage value.")
    quantity_ordered = graphene.Int(description="Total quantity ordered.")
    revenue = graphene.Field(
        TaxedMoney,
        period=graphene.Argument(ReportingPeriod),
        description=(
            "Total revenue generated by a variant in given period of time. Note: this "
            "field should be queried using `reportRoomSales` query as it uses "
            "optimizations suitable for such calculations."
        ),
    )
    images = graphene.List(
        lambda: RoomImage, description="List of images for the room variant."
    )
    translation = TranslationField(
        RoomVariantTranslation,
        type_name="room variant",
        resolver=ChannelContextType.resolve_translation,
    )
    digital_content = graphene.Field(
        DigitalContent, description="Digital content for the room variant."
    )
    stocks = graphene.Field(
        graphene.List(Stock),
        description="Stocks for the room variant.",
        country_code=graphene.Argument(
            CountryCodeEnum,
            description="Two-letter ISO 3166-1 country code.",
            required=False,
        ),
    )
    quantity_available = graphene.Int(
        required=True,
        description="Quantity of a room available for sale in one checkout.",
        country_code=graphene.Argument(
            CountryCodeEnum,
            description=(
                "Two-letter ISO 3166-1 country code. When provided, the exact quantity "
                "from a hotel operating in shipping zones that contain this "
                "country will be returned. Otherwise, it will return the maximum "
                "quantity from all shipping zones."
            ),
        ),
    )

    class Meta:
        default_resolver = ChannelContextType.resolver_with_context
        description = (
            "Represents a version of a room such as different size or color."
        )
        only_fields = ["id", "name", "room", "sku", "track_inventory"]
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.RoomVariant

    @staticmethod
    @one_of_permissions_required(
        [RoomPermissions.MANAGE_ROOMS, OrderPermissions.MANAGE_ORDERS]
    )
    def resolve_stocks(
        root: ChannelContext[models.RoomVariant], info, country_code=None
    ):
        if not country_code:
            return root.node.stocks.annotate_available_quantity()
        return root.node.stocks.for_country(country_code).annotate_available_quantity()

    @staticmethod
    def resolve_quantity_available(
        root: ChannelContext[models.RoomVariant], info, country_code=None
    ):
        if not root.node.track_inventory:
            return settings.MAX_CHECKOUT_LINE_QUANTITY

        return AvailableQuantityByRoomVariantIdAndCountryCodeLoader(
            info.context
        ).load((root.node.id, country_code))

    @staticmethod
    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_digital_content(root: ChannelContext[models.RoomVariant], *_args):
        return getattr(root.node, "digital_content", None)

    @staticmethod
    def resolve_attributes(
        root: ChannelContext[models.RoomVariant],
        info,
        variant_selection: Optional[str] = None,
    ):
        def apply_variant_selection_filter(selected_attributes):
            if not variant_selection or variant_selection == VariantAttributeScope.ALL:
                return selected_attributes
            attributes = [
                selected_att["attribute"] for selected_att in selected_attributes
            ]
            variant_selection_attrs = get_variant_selection_attributes(attributes)

            if variant_selection == VariantAttributeScope.VARIANT_SELECTION:
                return [
                    selected_attribute
                    for selected_attribute in selected_attributes
                    if selected_attribute["attribute"] in variant_selection_attrs
                ]
            return [
                selected_attribute
                for selected_attribute in selected_attributes
                if selected_attribute["attribute"] not in variant_selection_attrs
            ]

        return (
            SelectedAttributesByRoomVariantIdLoader(info.context)
            .load(root.node.id)
            .then(apply_variant_selection_filter)
        )

    @staticmethod
    @staff_member_or_app_required
    def resolve_channel_listings(
        root: ChannelContext[models.RoomVariant], info, **_kwargs
    ):
        return VariantChannelListingByVariantIdLoader(info.context).load(root.node.id)

    @staticmethod
    def resolve_pricing(root: ChannelContext[models.RoomVariant], info):
        if not root.channel_slug:
            return None

        channel_slug = str(root.channel_slug)
        context = info.context
        room = RoomByIdLoader(context).load(root.node.room_id)
        room_channel_listing = RoomChannelListingByRoomIdAndChannelSlugLoader(
            context
        ).load((root.node.room_id, channel_slug))
        variant_channel_listing = VariantChannelListingByVariantIdAndChannelSlugLoader(
            context
        ).load((root.node.id, channel_slug))
        collections = CollectionsByRoomIdLoader(context).load(root.node.room_id)
        channel = ChannelBySlugLoader(context).load(channel_slug)

        def calculate_pricing_info(discounts):
            def calculate_pricing_with_channel(channel):
                def calculate_pricing_with_room_variant_channel_listings(
                    variant_channel_listing,
                ):
                    def calculate_pricing_with_room(room):
                        def calculate_pricing_with_room_channel_listings(
                            room_channel_listing,
                        ):
                            def calculate_pricing_with_collections(collections):
                                if (
                                    not variant_channel_listing
                                    or not room_channel_listing
                                ):
                                    return None
                                availability = get_variant_availability(
                                    variant=root.node,
                                    variant_channel_listing=variant_channel_listing,
                                    room=room,
                                    room_channel_listing=room_channel_listing,
                                    collections=collections,
                                    discounts=discounts,
                                    channel=channel,
                                    country=context.country,
                                    local_currency=context.currency,
                                    plugins=context.plugins,
                                )
                                return VariantPricingInfo(**asdict(availability))

                            return collections.then(calculate_pricing_with_collections)

                        return room_channel_listing.then(
                            calculate_pricing_with_room_channel_listings
                        )

                    return room.then(calculate_pricing_with_room)

                return variant_channel_listing.then(
                    calculate_pricing_with_room_variant_channel_listings
                )

            return channel.then(calculate_pricing_with_channel)

        return (
            DiscountsByDateTimeLoader(context)
            .load(info.context.request_time)
            .then(calculate_pricing_info)
        )

    @staticmethod
    def resolve_room(root: ChannelContext[models.RoomVariant], info):
        room = RoomByIdLoader(info.context).load(root.node.room_id)
        return room.then(
            lambda room: ChannelContext(node=room, channel_slug=root.channel_slug)
        )

    @staticmethod
    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_quantity_ordered(root: ChannelContext[models.RoomVariant], *_args):
        # This field is added through annotation when using the
        # `resolve_report_room_sales` resolver.
        return getattr(root.node, "quantity_ordered", None)

    @staticmethod
    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_revenue(root: ChannelContext[models.RoomVariant], info, period):
        start_date = reporting_period_to_date(period)
        variant = root.node
        channel_slug = root.channel_slug

        def calculate_revenue_with_channel(channel):
            if not channel:
                return None

            def calculate_revenue_with_order_lines(order_lines):
                def calculate_revenue_with_orders(orders):
                    orders_dict = {order.id: order for order in orders}
                    return calculate_revenue_for_variant(
                        variant,
                        start_date,
                        order_lines,
                        orders_dict,
                        channel.currency_code,
                    )

                order_ids = [order_line.order_id for order_line in order_lines]
                return (
                    OrderByIdLoader(info.context)
                    .load_many(order_ids)
                    .then(calculate_revenue_with_orders)
                )

            return (
                OrderLinesByVariantIdAndChannelIdLoader(info.context)
                .load((variant.id, channel.id))
                .then(calculate_revenue_with_order_lines)
            )

        return (
            ChannelBySlugLoader(info.context)
            .load(channel_slug)
            .then(calculate_revenue_with_channel)
        )

    @staticmethod
    def resolve_images(root: ChannelContext[models.RoomVariant], info, *_args):
        return ImagesByRoomVariantIdLoader(info.context).load(root.node.id)

    @staticmethod
    def __resolve_reference(
        root: ChannelContext[models.RoomVariant], _info, **_kwargs
    ):
        return graphene.Node.get_node_from_global_id(_info, root.node.id)

    """
    @staticmethod
    def resolve_weight(root: ChannelContext[models.RoomVariant], _info, **_kwargs):
        return convert_weight_to_default_weight_unit(root.node.weight)
    """


@key(fields="id")
class Room(ChannelContextTypeWithMetadata, CountableDjangoObjectType):
    url = graphene.String(
        description="The storefront URL for the room.",
        required=True,
        deprecation_reason="This field will be removed after 2020-07-31.",
    )
    thumbnail = graphene.Field(
        Image,
        description="The main thumbnail for a room.",
        size=graphene.Argument(graphene.Int, description="Size of thumbnail."),
    )
    pricing = graphene.Field(
        RoomPricingInfo,
        description=(
            "Lists the storefront room's pricing, the current price and discounts, "
            "only meant for displaying."
        ),
    )
    is_available = graphene.Boolean(
        description="Whether the room is in stock and visible or not."
    )
    tax_type = graphene.Field(
        TaxType, description="A type of tax. Assigned by enabled tax gateway"
    )
    attributes = graphene.List(
        graphene.NonNull(SelectedAttribute),
        required=True,
        description="List of attributes assigned to this room.",
    )
    channel_listings = graphene.List(
        graphene.NonNull(RoomChannelListing),
        description="List of availability in channels for the room.",
    )
    image_by_id = graphene.Field(
        lambda: RoomImage,
        id=graphene.Argument(graphene.ID, description="ID of a room image."),
        description="Get a single room image by ID.",
    )
    variants = graphene.List(
        RoomVariant, description="List of variants for the room."
    )
    images = graphene.List(
        lambda: RoomImage, description="List of images for the room."
    )
    collections = graphene.List(
        lambda: Collection, description="List of collections for the room."
    )
    translation = TranslationField(
        RoomTranslation,
        type_name="room",
        resolver=ChannelContextType.resolve_translation,
    )
    available_for_purchase = graphene.Date(
        description="Date when room is available for purchase. "
    )
    is_available_for_purchase = graphene.Boolean(
        description="Whether the room is available for purchase."
    )

    class Meta:
        default_resolver = ChannelContextType.resolver_with_context
        description = "Represents an individual item for sale in the storefront."
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.Room
        only_fields = [
            "category",
            "charge_taxes",
            "description",
            "description_json",
            "id",
            "name",
            "slug",
            "room_type",
            "seo_description",
            "seo_title",
            "updated_at",
            # "weight",
            "default_variant",
            "rating",
        ]

    @staticmethod
    def resolve_default_variant(root: ChannelContext[models.Room], info):
        default_variant_id = root.node.default_variant_id
        if default_variant_id is None:
            return None

        def return_default_variant_with_channel_context(variant):
            return ChannelContext(node=variant, channel_slug=root.channel_slug)

        return (
            RoomVariantByIdLoader(info.context)
            .load(default_variant_id)
            .then(return_default_variant_with_channel_context)
        )

    @staticmethod
    def resolve_category(root: ChannelContext[models.Room], info):
        category_id = root.node.category_id
        if category_id is None:
            return None
        return CategoryByIdLoader(info.context).load(category_id)

    @staticmethod
    def resolve_tax_type(root: ChannelContext[models.Room], info):
        tax_data = info.context.plugins.get_tax_code_from_object_meta(root.node)
        return TaxType(tax_code=tax_data.code, description=tax_data.description)

    @staticmethod
    def resolve_thumbnail(root: ChannelContext[models.Room], info, *, size=255):
        def return_first_thumbnail(images):
            image = images[0] if images else None
            if image:
                url = get_room_image_thumbnail(image, size, method="thumbnail")
                alt = image.alt
                return Image(alt=alt, url=info.context.build_absolute_uri(url))
            return None

        return (
            ImagesByRoomIdLoader(info.context)
            .load(root.node.id)
            .then(return_first_thumbnail)
        )

    @staticmethod
    def resolve_url(*_args):
        return ""

    @staticmethod
    def resolve_pricing(root: ChannelContext[models.Room], info):
        if not root.channel_slug:
            return None

        context = info.context
        channel_slug = str(root.channel_slug)
        room_channel_listing = RoomChannelListingByRoomIdAndChannelSlugLoader(
            context
        ).load((root.node.id, channel_slug))
        variants = RoomVariantsByRoomIdLoader(context).load(root.node.id)
        variants_channel_listing = VariantsChannelListingByRoomIdAndChanneSlugLoader(
            context
        ).load((root.node.id, channel_slug))
        collections = CollectionsByRoomIdLoader(context).load(root.node.id)
        channel = ChannelBySlugLoader(context).load(channel_slug)

        def calculate_pricing_info(discounts):
            def calculate_pricing_with_channel(channel):
                def calculate_pricing_with_room_channel_listings(
                    room_channel_listing,
                ):
                    def calculate_pricing_with_variants(variants):
                        def calculate_pricing_with_variants_channel_listings(
                            variants_channel_listing,
                        ):
                            def calculate_pricing_with_collections(collections):
                                if not variants_channel_listing:
                                    return None
                                availability = get_room_availability(
                                    room=root.node,
                                    room_channel_listing=room_channel_listing,
                                    variants=variants,
                                    variants_channel_listing=variants_channel_listing,
                                    collections=collections,
                                    discounts=discounts,
                                    channel=channel,
                                    country=context.country,
                                    local_currency=context.currency,
                                    plugins=context.plugins,
                                )
                                return RoomPricingInfo(**asdict(availability))

                            return collections.then(calculate_pricing_with_collections)

                        return variants_channel_listing.then(
                            calculate_pricing_with_variants_channel_listings
                        )

                    return variants.then(calculate_pricing_with_variants)

                return room_channel_listing.then(
                    calculate_pricing_with_room_channel_listings
                )

            return channel.then(calculate_pricing_with_channel)

        return (
            DiscountsByDateTimeLoader(context)
            .load(info.context.request_time)
            .then(calculate_pricing_info)
        )

    @staticmethod
    def resolve_is_available(root: ChannelContext[models.Room], info):
        if not root.channel_slug:
            return None
        channel_slug = str(root.channel_slug)

        def calculate_is_available(room_channel_listing):
            country = info.context.country
            in_stock = is_room_in_stock(root.node, country)
            is_visible = False
            if room_channel_listing:
                is_visible = room_channel_listing.is_available_for_purchase()
            return is_visible and in_stock

        return (
            RoomChannelListingByRoomIdAndChannelSlugLoader(info.context)
            .load((root.node.id, channel_slug))
            .then(calculate_is_available)
        )

    @staticmethod
    def resolve_attributes(root: ChannelContext[models.Room], info):
        return SelectedAttributesByRoomIdLoader(info.context).load(root.node.id)

    @staticmethod
    def resolve_image_by_id(root: ChannelContext[models.Room], info, id):
        pk = get_database_id(info, id, RoomImage)
        try:
            return root.node.images.get(pk=pk)
        except models.RoomImage.DoesNotExist:
            raise GraphQLError("Room image not found.")

    @staticmethod
    def resolve_images(root: ChannelContext[models.Room], info, **_kwargs):
        return ImagesByRoomIdLoader(info.context).load(root.node.id)

    @staticmethod
    def resolve_variants(root: ChannelContext[models.Room], info, **_kwargs):
        return (
            RoomVariantsByRoomIdLoader(info.context)
            .load(root.node.id)
            .then(
                lambda variants: [
                    ChannelContext(node=variant, channel_slug=root.channel_slug)
                    for variant in variants
                ]
            )
        )

    @staticmethod
    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_channel_listings(root: ChannelContext[models.Room], info, **_kwargs):
        return RoomChannelListingByRoomIdLoader(info.context).load(root.node.id)

    @staticmethod
    def resolve_collections(root: ChannelContext[models.Room], info, **_kwargs):
        requestor = get_user_or_app_from_context(info.context)
        is_staff = requestor_is_staff_member_or_app(requestor)

        def return_collections(collections):
            if is_staff:
                return [
                    ChannelContext(node=collection, channel_slug=root.channel_slug)
                    for collection in collections
                ]

            dataloader_keys = [
                (collection.id, str(root.channel_slug)) for collection in collections
            ]
            CollectionChannelListingLoader = (
                CollectionChannelListingByCollectionIdAndChannelSlugLoader
            )
            channel_listings = CollectionChannelListingLoader(info.context).load_many(
                dataloader_keys
            )

            def return_visible_collections(channel_listings):
                visible_collections = []
                channel_listings_dict = {
                    channel_listing.collection_id: channel_listing
                    for channel_listing in channel_listings
                    if channel_listing
                }

                for collection in collections:
                    channel_listing = channel_listings_dict.get(collection.id)
                    if channel_listing and channel_listing.is_visible:
                        visible_collections.append(collection)

                return [
                    ChannelContext(node=collection, channel_slug=root.channel_slug)
                    for collection in visible_collections
                ]

            return channel_listings.then(return_visible_collections)

        return (
            CollectionsByRoomIdLoader(info.context)
            .load(root.node.id)
            .then(return_collections)
        )

    @staticmethod
    def __resolve_reference(root: ChannelContext[models.Room], _info, **_kwargs):
        return graphene.Node.get_node_from_global_id(_info, root.node.id)

    @staticmethod
    def resolve_weight(root: ChannelContext[models.Room], _info, **_kwargs):
        return convert_weight_to_default_weight_unit(root.node.weight)

    @staticmethod
    def resolve_is_available_for_purchase(root: ChannelContext[models.Room], info):
        if not root.channel_slug:
            return None
        channel_slug = str(root.channel_slug)

        def calculate_is_available_for_purchase(room_channel_listing):
            if not room_channel_listing:
                return None
            return room_channel_listing.is_available_for_purchase()

        return (
            RoomChannelListingByRoomIdAndChannelSlugLoader(info.context)
            .load((root.node.id, channel_slug))
            .then(calculate_is_available_for_purchase)
        )

    @staticmethod
    def resolve_available_for_purchase(root: ChannelContext[models.Room], info):
        if not root.channel_slug:
            return None
        channel_slug = str(root.channel_slug)

        def calculate_available_for_purchase(room_channel_listing):
            if not room_channel_listing:
                return None
            return room_channel_listing.available_for_purchase

        return (
            RoomChannelListingByRoomIdAndChannelSlugLoader(info.context)
            .load((root.node.id, channel_slug))
            .then(calculate_available_for_purchase)
        )

    @staticmethod
    def resolve_room_type(root: ChannelContext[models.Room], info):
        return RoomTypeByIdLoader(info.context).load(root.node.room_type_id)


@key(fields="id")
class RoomType(CountableDjangoObjectType):
    rooms = ChannelContextFilterConnectionField(
        Room,
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
        description="List of rooms of this type.",
        deprecation_reason=(
            "Use the top-level `rooms` query with the `roomTypes` filter."
        ),
    )
    tax_rate = TaxRateType(description="A type of tax rate.")
    tax_type = graphene.Field(
        TaxType, description="A type of tax. Assigned by enabled tax gateway"
    )
    variant_attributes = graphene.List(
        Attribute,
        description="Variant attributes of that room type.",
        variant_selection=graphene.Argument(
            VariantAttributeScope,
            description="Define scope of returned attributes.",
        ),
    )
    room_attributes = graphene.List(
        Attribute, description="Room attributes of that room type."
    )
    available_attributes = FilterInputConnectionField(
        Attribute, filter=AttributeFilterInput()
    )

    class Meta:
        description = (
            "Represents a type of room. It defines what attributes are available to "
            "rooms of this type."
        )
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.RoomType
        only_fields = [
            "has_variants",
            "id",
            "is_digital",
            "is_shipping_required",
            "name",
            "slug",
            # "weight",
            "tax_type",
        ]

    @staticmethod
    def resolve_tax_type(root: models.RoomType, info):
        tax_data = info.context.plugins.get_tax_code_from_object_meta(root)
        return TaxType(tax_code=tax_data.code, description=tax_data.description)

    @staticmethod
    def resolve_tax_rate(root: models.RoomType, _info, **_kwargs):
        # FIXME this resolver should be dropped after we drop tax_rate from API
        if not hasattr(root, "meta"):
            return None
        return root.get_value_from_metadata("vatlayer.code")

    @staticmethod
    def resolve_room_attributes(root: models.RoomType, info):
        return RoomAttributesByRoomTypeIdLoader(info.context).load(root.pk)

    @staticmethod
    def resolve_variant_attributes(
        root: models.RoomType,
        info,
        variant_selection: Optional[str] = None,
    ):
        def apply_variant_selection_filter(attributes):
            if not variant_selection or variant_selection == VariantAttributeScope.ALL:
                return attributes
            variant_selection_attrs = get_variant_selection_attributes(attributes)
            if variant_selection == VariantAttributeScope.VARIANT_SELECTION:
                return variant_selection_attrs
            return [attr for attr in attributes if attr not in variant_selection_attrs]

        return (
            VariantAttributesByRoomTypeIdLoader(info.context)
            .load(root.pk)
            .then(apply_variant_selection_filter)
        )

    @staticmethod
    def resolve_rooms(root: models.RoomType, info, channel=None, **_kwargs):
        requestor = get_user_or_app_from_context(info.context)
        if channel is None:
            channel = get_default_channel_slug_or_graphql_error()
        qs = root.rooms.visible_to_user(requestor, channel)
        return ChannelQsContext(qs=qs, channel_slug=channel)

    @staticmethod
    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_available_attributes(root: models.RoomType, info, **kwargs):
        qs = attribute_models.Attribute.objects.get_unassigned_room_type_attributes(
            root.pk
        )
        return resolve_attributes(info, qs=qs, **kwargs)

    @staticmethod
    def __resolve_reference(root, _info, **_kwargs):
        return graphene.Node.get_node_from_global_id(_info, root.id)

    @staticmethod
    def resolve_weight(root: models.RoomType, _info, **_kwargs):
        return convert_weight_to_default_weight_unit(root.weight)


@key(fields="id")
class Collection(ChannelContextTypeWithMetadata, CountableDjangoObjectType):
    rooms = ChannelContextFilterConnectionField(
        Room,
        filter=RoomFilterInput(description="Filtering options for rooms."),
        sort_by=RoomOrder(description="Sort rooms."),
        description="List of rooms in this collection.",
    )
    background_image = graphene.Field(
        Image, size=graphene.Int(description="Size of the image.")
    )
    translation = TranslationField(
        CollectionTranslation,
        type_name="collection",
        resolver=ChannelContextType.resolve_translation,
    )
    channel_listings = graphene.List(
        graphene.NonNull(CollectionChannelListing),
        description="List of channels in which the collection is available.",
    )

    class Meta:
        default_resolver = ChannelContextType.resolver_with_context
        description = "Represents a collection of rooms."
        only_fields = [
            "description",
            "description_json",
            "id",
            "name",
            "seo_description",
            "seo_title",
            "slug",
        ]
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.Collection

    @staticmethod
    def resolve_background_image(
        root: ChannelContext[models.Collection], info, size=None, **_kwargs
    ):
        if root.node.background_image:
            node = root.node
            return Image.get_adjusted(
                image=node.background_image,
                alt=node.background_image_alt,
                size=size,
                rendition_key_set="background_images",
                info=info,
            )

    @staticmethod
    def resolve_rooms(root: ChannelContext[models.Collection], info, **kwargs):
        requestor = get_user_or_app_from_context(info.context)
        qs = root.node.rooms.visible_to_user(requestor, root.channel_slug)
        return ChannelQsContext(qs=qs, channel_slug=root.channel_slug)

    @staticmethod
    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_channel_listings(root: ChannelContext[models.Collection], info):
        return CollectionChannelListingByCollectionIdLoader(info.context).load(
            root.node.id
        )

    @staticmethod
    def __resolve_reference(root, _info, **_kwargs):
        return graphene.Node.get_node_from_global_id(_info, root.id)


@key(fields="id")
class Category(CountableDjangoObjectType):
    ancestors = PrefetchingConnectionField(
        lambda: Category, description="List of ancestors of the category."
    )
    rooms = ChannelContextFilterConnectionField(
        Room,
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
        description="List of rooms in the category.",
    )
    url = graphene.String(
        description="The storefront's URL for the category.",
        deprecation_reason="This field will be removed after 2020-07-31.",
    )
    children = PrefetchingConnectionField(
        lambda: Category, description="List of children of the category."
    )
    background_image = graphene.Field(
        Image, size=graphene.Int(description="Size of the image.")
    )
    translation = TranslationField(CategoryTranslation, type_name="category")

    class Meta:
        description = (
            "Represents a single category of rooms. Categories allow to organize "
            "rooms in a tree-hierarchies which can be used for navigation in the "
            "storefront."
        )
        only_fields = [
            "description",
            "description_json",
            "id",
            "level",
            "name",
            "parent",
            "seo_description",
            "seo_title",
            "slug",
        ]
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.Category

    @staticmethod
    def resolve_ancestors(root: models.Category, info, **_kwargs):
        return root.get_ancestors()

    @staticmethod
    def resolve_background_image(root: models.Category, info, size=None, **_kwargs):
        if root.background_image:
            return Image.get_adjusted(
                image=root.background_image,
                alt=root.background_image_alt,
                size=size,
                rendition_key_set="background_images",
                info=info,
            )

    @staticmethod
    def resolve_children(root: models.Category, info, **_kwargs):
        return root.children.all()

    @staticmethod
    def resolve_url(root: models.Category, _info):
        return ""

    @staticmethod
    def resolve_rooms(root: models.Category, info, channel=None, **_kwargs):
        requestor = get_user_or_app_from_context(info.context)
        is_staff = requestor_is_staff_member_or_app(requestor)
        tree = root.get_descendants(include_self=True)
        if channel is None and not is_staff:
            channel = get_default_channel_slug_or_graphql_error()
        qs = models.Room.objects.all()
        if not is_staff:
            qs = (
                qs.published(channel)
                .annotate_visible_in_listings(channel)
                .exclude(
                    visible_in_listings=False,
                )
            )
        if channel and is_staff:
            qs = qs.filter(channel_listings__channel__slug=channel)
        qs = qs.filter(category__in=tree)
        return ChannelQsContext(qs=qs, channel_slug=channel)

    @staticmethod
    def __resolve_reference(root, _info, **_kwargs):
        return graphene.Node.get_node_from_global_id(_info, root.id)


@key(fields="id")
class RoomImage(CountableDjangoObjectType):
    url = graphene.String(
        required=True,
        description="The URL of the image.",
        size=graphene.Int(description="Size of the image."),
    )

    class Meta:
        description = "Represents a room image."
        only_fields = ["alt", "id", "sort_order"]
        interfaces = [relay.Node]
        model = models.RoomImage

    @staticmethod
    def resolve_url(root: models.RoomImage, info, *, size=None):
        if size:
            url = get_thumbnail(root.image, size, method="thumbnail")
        else:
            url = root.image.url
        return info.context.build_absolute_uri(url)

    @staticmethod
    def __resolve_reference(root, _info, **_kwargs):
        return graphene.Node.get_node_from_global_id(_info, root.id)