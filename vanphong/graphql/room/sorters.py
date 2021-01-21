import graphene
from django.db.models import (
    BooleanField,
    Count,
    DateField,
    ExpressionWrapper,
    F,
    IntegerField,
    Min,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
)
from django.db.models.expressions import Window
from django.db.models.functions import Coalesce, DenseRank

from ...room.models import (
    Category,
    CollectionChannelListing,
    Room,
    RoomChannelListing,
)
from ..channel.sorters import validate_channel_slug
from ..core.types import ChannelSortInputObjectType, SortInputObjectType


class CategorySortField(graphene.Enum):
    NAME = ["name", "slug"]
    ROOM_COUNT = ["room_count", "name", "slug"]
    SUBCATEGORY_COUNT = ["subcategory_count", "name", "slug"]

    @property
    def description(self):
        # pylint: disable=no-member
        if self in [
            CategorySortField.NAME,
            CategorySortField.ROOM_COUNT,
            CategorySortField.SUBCATEGORY_COUNT,
        ]:
            sort_name = self.name.lower().replace("_", " ")
            return f"Sort categories by {sort_name}."
        raise ValueError("Unsupported enum value: %s" % self.value)

    @staticmethod
    def qs_with_room_count(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(
            room_count=Coalesce(
                Subquery(
                    Category.tree.add_related_count(
                        queryset, Room, "category", "p_c", cumulative=True
                    )
                    .values("p_c")
                    .filter(pk=OuterRef("pk"))[:1]
                ),
                0,
                output_field=IntegerField(),
            )
        )

    @staticmethod
    def qs_with_subcategory_count(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(subcategory_count=Count("children__id"))


class CategorySortingInput(ChannelSortInputObjectType):
    class Meta:
        sort_enum = CategorySortField
        type_name = "categories"


class CollectionSortField(graphene.Enum):
    NAME = ["name"]
    AVAILABILITY = ["is_published", "name"]
    ROOM_COUNT = ["room_count", "name"]
    PUBLICATION_DATE = ["publication_date", "name"]

    @property
    def description(self):
        # pylint: disable=no-member
        if self in [
            CollectionSortField.NAME,
            CollectionSortField.AVAILABILITY,
            CollectionSortField.ROOM_COUNT,
            CollectionSortField.PUBLICATION_DATE,
        ]:
            sort_name = self.name.lower().replace("_", " ")
            return f"Sort collections by {sort_name}."
        raise ValueError("Unsupported enum value: %s" % self.value)

    @staticmethod
    def qs_with_room_count(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(room_count=Count("collectionroom__id"))

    @staticmethod
    def qs_with_availability(queryset: QuerySet, channel_slug: str) -> QuerySet:
        validate_channel_slug(channel_slug)
        subquery = Subquery(
            CollectionChannelListing.objects.filter(
                collection_id=OuterRef("pk"), channel__slug=channel_slug
            ).values_list("is_published")[:1]
        )
        return queryset.annotate(
            is_published=ExpressionWrapper(subquery, output_field=BooleanField())
        )

    @staticmethod
    def qs_with_publication_date(queryset: QuerySet, channel_slug: str) -> QuerySet:
        validate_channel_slug(channel_slug)
        subquery = Subquery(
            CollectionChannelListing.objects.filter(
                collection_id=OuterRef("pk"), channel__slug=channel_slug
            ).values_list("publication_date")[:1]
        )
        return queryset.annotate(
            publication_date=ExpressionWrapper(subquery, output_field=DateField())
        )


class CollectionSortingInput(ChannelSortInputObjectType):
    class Meta:
        sort_enum = CollectionSortField
        type_name = "collections"


class RoomOrderField(graphene.Enum):
    NAME = ["name", "slug"]
    PRICE = ["min_variants_price_amount", "name", "slug"]
    MINIMAL_PRICE = ["discounted_price_amount", "name", "slug"]
    DATE = ["updated_at", "name", "slug"]
    TYPE = ["room_type__name", "name", "slug"]
    PUBLISHED = ["is_published", "name", "slug"]
    PUBLICATION_DATE = ["publication_date", "name", "slug"]
    COLLECTION = ["sort_order"]
    RATING = ["rating", "name", "slug"]

    @property
    def description(self):
        # pylint: disable=no-member
        descriptions = {
            RoomOrderField.COLLECTION.name: (
                "collection. Note: "
                "This option is available only for the `Collection.rooms` query."
            ),
            RoomOrderField.NAME.name: "name.",
            RoomOrderField.PRICE.name: "price.",
            RoomOrderField.TYPE.name: "type.",
            RoomOrderField.MINIMAL_PRICE.name: (
                "a minimal price of a room's variant."
            ),
            RoomOrderField.DATE.name: "update date.",
            RoomOrderField.PUBLISHED.name: "publication status.",
            RoomOrderField.PUBLICATION_DATE.name: "publication date.",
            RoomOrderField.RATING.name: "rating.",
        }
        if self.name in descriptions:
            return f"Sort rooms by {descriptions[self.name]}"
        raise ValueError("Unsupported enum value: %s" % self.value)

    @staticmethod
    def qs_with_price(queryset: QuerySet, channel_slug: str) -> QuerySet:
        validate_channel_slug(channel_slug)
        return queryset.annotate(
            min_variants_price_amount=Min(
                "variants__channel_listings__price_amount",
                filter=Q(variants__channel_listings__channel__slug=channel_slug),
            )
        )

    @staticmethod
    def qs_with_minimal_price(queryset: QuerySet, channel_slug: str) -> QuerySet:
        validate_channel_slug(channel_slug)
        return queryset.annotate(
            discounted_price_amount=Min(
                "channel_listings__discounted_price_amount",
                filter=Q(channel_listings__channel__slug=channel_slug),
            )
        )

    @staticmethod
    def qs_with_published(queryset: QuerySet, channel_slug: str) -> QuerySet:
        validate_channel_slug(channel_slug)
        subquery = Subquery(
            RoomChannelListing.objects.filter(
                room_id=OuterRef("pk"), channel__slug=channel_slug
            ).values_list("is_published")[:1]
        )
        return queryset.annotate(
            is_published=ExpressionWrapper(subquery, output_field=BooleanField())
        )

    @staticmethod
    def qs_with_publication_date(queryset: QuerySet, channel_slug: str) -> QuerySet:
        validate_channel_slug(channel_slug)
        subquery = Subquery(
            RoomChannelListing.objects.filter(
                room_id=OuterRef("pk"), channel__slug=channel_slug
            ).values_list("publication_date")[:1]
        )
        return queryset.annotate(
            publication_date=ExpressionWrapper(subquery, output_field=DateField())
        )

    @staticmethod
    def qs_with_collection(queryset: QuerySet, **_kwargs) -> QuerySet:
        return queryset.annotate(
            sort_order=Window(
                expression=DenseRank(),
                order_by=(
                    F("collectionroom__sort_order").asc(nulls_last=True),
                    F("collectionroom__id"),
                ),
            )
        )


class RoomOrder(ChannelSortInputObjectType):
    attribute_id = graphene.Argument(
        graphene.ID,
        description=(
            "Sort room by the selected attribute's values.\n"
            "Note: this doesn't take translations into account yet."
        ),
    )
    field = graphene.Argument(
        RoomOrderField, description="Sort rooms by the selected field."
    )

    class Meta:
        sort_enum = RoomOrderField


class RoomTypeSortField(graphene.Enum):
    NAME = ["name", "slug"]
    DIGITAL = ["is_digital", "name", "slug"]
    SHIPPING_REQUIRED = ["is_shipping_required", "name", "slug"]

    @property
    def description(self):
        # pylint: disable=no-member
        descriptions = {
            RoomTypeSortField.NAME.name: "name",
            RoomTypeSortField.DIGITAL.name: "type",
            RoomTypeSortField.SHIPPING_REQUIRED.name: "shipping",
        }
        if self.name in descriptions:
            return f"Sort rooms by {descriptions[self.name]}."
        raise ValueError("Unsupported enum value: %s" % self.value)


class RoomTypeSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = RoomTypeSortField
        type_name = "room types"
