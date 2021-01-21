import graphene

from ...account.utils import requestor_is_staff_member_or_app
from ...core.permissions import RoomPermissions
from ..channel import ChannelContext
from ..channel.utils import get_default_channel_slug_or_graphql_error
from ..core.enums import ReportingPeriod
from ..core.fields import (
    ChannelContextFilterConnectionField,
    FilterInputConnectionField,
    PrefetchingConnectionField,
)
from ..core.validators import validate_one_of_args_is_in_query
from ..decorators import permission_required
from ..translations.mutations import (
    CategoryTranslate,
    CollectionTranslate,
    RoomTranslate,
    RoomVariantTranslate,
)
from ..utils import get_user_or_app_from_context
from .bulk_mutations.rooms import (
    CategoryBulkDelete,
    CollectionBulkDelete,
    RoomBulkDelete,
    RoomImageBulkDelete,
    RoomTypeBulkDelete,
    RoomVariantBulkCreate,
    RoomVariantBulkDelete,
    RoomVariantStocksCreate,
    RoomVariantStocksDelete,
    RoomVariantStocksUpdate,
)
from .enums import StockAvailability
from .filters import (
    CategoryFilterInput,
    CollectionFilterInput,
    RoomFilterInput,
    RoomTypeFilterInput,
    RoomVariantFilterInput,
)
from .mutations.attributes import (
    RoomAttributeAssign,
    RoomAttributeUnassign,
    RoomTypeReorderAttributes,
)
from .mutations.channels import (
    CollectionChannelListingUpdate,
    RoomChannelListingUpdate,
    RoomVariantChannelListingUpdate,
)
from .mutations.digital_contents import (
    DigitalContentCreate,
    DigitalContentDelete,
    DigitalContentUpdate,
    DigitalContentUrlCreate,
)
from .mutations.rooms import (
    CategoryCreate,
    CategoryDelete,
    CategoryUpdate,
    CollectionAddRooms,
    CollectionCreate,
    CollectionDelete,
    CollectionRemoveRooms,
    CollectionReorderRooms,
    CollectionUpdate,
    RoomCreate,
    RoomDelete,
    RoomImageCreate,
    RoomImageDelete,
    RoomImageReorder,
    RoomImageUpdate,
    RoomTypeCreate,
    RoomTypeDelete,
    RoomTypeUpdate,
    RoomUpdate,
    RoomVariantCreate,
    RoomVariantDelete,
    RoomVariantReorder,
    RoomVariantSetDefault,
    RoomVariantUpdate,
    VariantImageAssign,
    VariantImageUnassign,
)
from .resolvers import (
    resolve_categories,
    resolve_category_by_slug,
    resolve_collection_by_id,
    resolve_collection_by_slug,
    resolve_collections,
    resolve_digital_contents,
    resolve_room_by_id,
    resolve_room_by_slug,
    resolve_room_types,
    resolve_room_variant_by_sku,
    resolve_room_variants,
    resolve_rooms,
    resolve_report_room_sales,
    resolve_variant_by_id,
)
from .sorters import (
    CategorySortingInput,
    CollectionSortingInput,
    RoomOrder,
    RoomTypeSortingInput,
)
from .types import (
    Category,
    Collection,
    DigitalContent,
    Room,
    RoomType,
    RoomVariant,
)


class RoomQueries(graphene.ObjectType):
    digital_content = graphene.Field(
        DigitalContent,
        description="Look up digital content by ID.",
        id=graphene.Argument(
            graphene.ID, description="ID of the digital content.", required=True
        ),
    )
    digital_contents = PrefetchingConnectionField(
        DigitalContent, description="List of digital content."
    )
    categories = FilterInputConnectionField(
        Category,
        filter=CategoryFilterInput(description="Filtering options for categories."),
        sort_by=CategorySortingInput(description="Sort categories."),
        level=graphene.Argument(
            graphene.Int,
            description="Filter categories by the nesting level in the category tree.",
        ),
        description="List of the shop's categories.",
    )
    category = graphene.Field(
        Category,
        id=graphene.Argument(graphene.ID, description="ID of the category."),
        slug=graphene.Argument(graphene.String, description="Slug of the category"),
        description="Look up a category by ID or slug.",
    )
    collection = graphene.Field(
        Collection,
        id=graphene.Argument(
            graphene.ID,
            description="ID of the collection.",
        ),
        slug=graphene.Argument(graphene.String, description="Slug of the category"),
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
        description="Look up a collection by ID.",
    )
    collections = ChannelContextFilterConnectionField(
        Collection,
        filter=CollectionFilterInput(description="Filtering options for collections."),
        sort_by=CollectionSortingInput(description="Sort collections."),
        description="List of the shop's collections.",
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
    )
    room = graphene.Field(
        Room,
        id=graphene.Argument(
            graphene.ID,
            description="ID of the room.",
        ),
        slug=graphene.Argument(graphene.String, description="Slug of the room."),
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
        description="Look up a room by ID.",
    )
    rooms = ChannelContextFilterConnectionField(
        Room,
        filter=RoomFilterInput(description="Filtering options for rooms."),
        sort_by=RoomOrder(description="Sort rooms."),
        stock_availability=graphene.Argument(
            StockAvailability,
            description=(
                "[Deprecated] Filter rooms by stock availability. Use the `filter` "
                "field instead. This field will be removed after 2020-07-31."
            ),
        ),
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
        description="List of the shop's rooms.",
    )
    room_type = graphene.Field(
        RoomType,
        id=graphene.Argument(
            graphene.ID, description="ID of the room type.", required=True
        ),
        description="Look up a room type by ID.",
    )
    room_types = FilterInputConnectionField(
        RoomType,
        filter=RoomTypeFilterInput(
            description="Filtering options for room types."
        ),
        sort_by=RoomTypeSortingInput(description="Sort room types."),
        description="List of the shop's room types.",
    )
    room_variant = graphene.Field(
        RoomVariant,
        id=graphene.Argument(
            graphene.ID,
            description="ID of the room variant.",
        ),
        sku=graphene.Argument(
            graphene.String, description="Sku of the room variant."
        ),
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
        description="Look up a room variant by ID or SKU.",
    )
    room_variants = ChannelContextFilterConnectionField(
        RoomVariant,
        ids=graphene.List(
            graphene.ID, description="Filter room variants by given IDs."
        ),
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned."
        ),
        filter=RoomVariantFilterInput(
            description="Filtering options for room variant."
        ),
        description="List of room variants.",
    )
    report_room_sales = ChannelContextFilterConnectionField(
        RoomVariant,
        period=graphene.Argument(
            ReportingPeriod, required=True, description="Span of time."
        ),
        channel=graphene.String(
            description="Slug of a channel for which the data should be returned.",
            required=True,
        ),
        description="List of top selling rooms.",
    )

    def resolve_categories(self, info, level=None, **kwargs):
        return resolve_categories(info, level=level, **kwargs)

    def resolve_category(self, info, id=None, slug=None, **kwargs):
        validate_one_of_args_is_in_query("id", id, "slug", slug)
        if id:
            return graphene.Node.get_node_from_global_id(info, id, Category)
        if slug:
            return resolve_category_by_slug(slug=slug)

    def resolve_collection(self, info, id=None, slug=None, channel=None, **_kwargs):
        validate_one_of_args_is_in_query("id", id, "slug", slug)
        requestor = get_user_or_app_from_context(info.context)

        is_staff = requestor_is_staff_member_or_app(requestor)
        if channel is None and not is_staff:
            channel = get_default_channel_slug_or_graphql_error()
        if id:
            _, id = graphene.Node.from_global_id(id)
            collection = resolve_collection_by_id(info, id, channel, requestor)
        else:
            collection = resolve_collection_by_slug(
                info, slug=slug, channel_slug=channel, requestor=requestor
            )
        return (
            ChannelContext(node=collection, channel_slug=channel)
            if collection
            else None
        )

    def resolve_collections(self, info, channel=None, *_args, **_kwargs):
        requestor = get_user_or_app_from_context(info.context)
        is_staff = requestor_is_staff_member_or_app(requestor)
        if channel is None and not is_staff:
            channel = get_default_channel_slug_or_graphql_error()
        return resolve_collections(info, channel)

    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_digital_content(self, info, id):
        return graphene.Node.get_node_from_global_id(info, id, DigitalContent)

    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_digital_contents(self, info, **_kwargs):
        return resolve_digital_contents(info)

    def resolve_room(self, info, id=None, slug=None, channel=None, **_kwargs):
        validate_one_of_args_is_in_query("id", id, "slug", slug)
        requestor = get_user_or_app_from_context(info.context)
        is_staff = requestor_is_staff_member_or_app(requestor)

        if channel is None and not is_staff:
            channel = get_default_channel_slug_or_graphql_error()
        if id:
            _, id = graphene.Node.from_global_id(id)
            room = resolve_room_by_id(
                info, id, channel_slug=channel, requestor=requestor
            )
        else:
            room = resolve_room_by_slug(
                info, room_slug=slug, channel_slug=channel, requestor=requestor
            )
        return ChannelContext(node=room, channel_slug=channel) if room else None

    def resolve_rooms(self, info, channel=None, **kwargs):
        requestor = get_user_or_app_from_context(info.context)
        if channel is None and not requestor_is_staff_member_or_app(requestor):
            channel = get_default_channel_slug_or_graphql_error()
        return resolve_rooms(info, requestor, channel_slug=channel, **kwargs)

    def resolve_room_type(self, info, id, **_kwargs):
        return graphene.Node.get_node_from_global_id(info, id, RoomType)

    def resolve_room_types(self, info, **kwargs):
        return resolve_room_types(info, **kwargs)

    def resolve_room_variant(
        self,
        info,
        id=None,
        sku=None,
        channel=None,
    ):
        validate_one_of_args_is_in_query("id", id, "sku", sku)
        requestor = get_user_or_app_from_context(info.context)
        is_staff = requestor_is_staff_member_or_app(requestor)
        if channel is None and not is_staff:
            channel = get_default_channel_slug_or_graphql_error()
        if id:
            _, id = graphene.Node.from_global_id(id)
            variant = resolve_variant_by_id(
                info, id, channel_slug=channel, requestor=requestor
            )
        else:
            variant = resolve_room_variant_by_sku(
                info,
                sku=sku,
                channel_slug=channel,
                requestor=requestor,
                requestor_has_access_to_all=is_staff,
            )
        return ChannelContext(node=variant, channel_slug=channel) if variant else None

    def resolve_room_variants(self, info, ids=None, channel=None, **_kwargs):
        requestor = get_user_or_app_from_context(info.context)
        is_staff = requestor_is_staff_member_or_app(requestor)
        if channel is None and not is_staff:
            channel = get_default_channel_slug_or_graphql_error()
        return resolve_room_variants(
            info,
            ids=ids,
            channel_slug=channel,
            requestor_has_access_to_all=is_staff,
            requestor=requestor,
        )

    @permission_required(RoomPermissions.MANAGE_ROOMS)
    def resolve_report_room_sales(self, *_args, period, channel, **_kwargs):
        return resolve_report_room_sales(period, channel_slug=channel)


class RoomMutations(graphene.ObjectType):
    room_attribute_assign = RoomAttributeAssign.Field()
    room_attribute_unassign = RoomAttributeUnassign.Field()

    category_create = CategoryCreate.Field()
    category_delete = CategoryDelete.Field()
    category_bulk_delete = CategoryBulkDelete.Field()
    category_update = CategoryUpdate.Field()
    category_translate = CategoryTranslate.Field()

    collection_add_rooms = CollectionAddRooms.Field()
    collection_create = CollectionCreate.Field()
    collection_delete = CollectionDelete.Field()
    collection_reorder_rooms = CollectionReorderRooms.Field()
    collection_bulk_delete = CollectionBulkDelete.Field()
    collection_remove_rooms = CollectionRemoveRooms.Field()
    collection_update = CollectionUpdate.Field()
    collection_translate = CollectionTranslate.Field()
    collection_channel_listing_update = CollectionChannelListingUpdate.Field()

    room_create = RoomCreate.Field()
    room_delete = RoomDelete.Field()
    room_bulk_delete = RoomBulkDelete.Field()
    room_update = RoomUpdate.Field()
    room_translate = RoomTranslate.Field()

    room_channel_listing_update = RoomChannelListingUpdate.Field()

    room_image_create = RoomImageCreate.Field()
    room_variant_reorder = RoomVariantReorder.Field()
    room_image_delete = RoomImageDelete.Field()
    room_image_bulk_delete = RoomImageBulkDelete.Field()
    room_image_reorder = RoomImageReorder.Field()
    room_image_update = RoomImageUpdate.Field()

    room_type_create = RoomTypeCreate.Field()
    room_type_delete = RoomTypeDelete.Field()
    room_type_bulk_delete = RoomTypeBulkDelete.Field()
    room_type_update = RoomTypeUpdate.Field()
    room_type_reorder_attributes = RoomTypeReorderAttributes.Field()

    digital_content_create = DigitalContentCreate.Field()
    digital_content_delete = DigitalContentDelete.Field()
    digital_content_update = DigitalContentUpdate.Field()

    digital_content_url_create = DigitalContentUrlCreate.Field()

    room_variant_create = RoomVariantCreate.Field()
    room_variant_delete = RoomVariantDelete.Field()
    room_variant_bulk_create = RoomVariantBulkCreate.Field()
    room_variant_bulk_delete = RoomVariantBulkDelete.Field()
    room_variant_stocks_create = RoomVariantStocksCreate.Field()
    room_variant_stocks_delete = RoomVariantStocksDelete.Field()
    room_variant_stocks_update = RoomVariantStocksUpdate.Field()
    room_variant_update = RoomVariantUpdate.Field()
    room_variant_set_default = RoomVariantSetDefault.Field()
    room_variant_translate = RoomVariantTranslate.Field()
    room_variant_channel_listing_update = RoomVariantChannelListingUpdate.Field()

    variant_image_assign = VariantImageAssign.Field()
    variant_image_unassign = VariantImageUnassign.Field()
