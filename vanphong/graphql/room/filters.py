from collections import defaultdict
from typing import Dict, Iterable, List, Optional

import django_filters
import graphene
from django.db.models import Exists, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from graphene_django.filter import GlobalIDFilter, GlobalIDMultipleChoiceFilter

from ...attribute.models import (
    AssignedRoomAttribute,
    AssignedVariantAttribute,
    Attribute,
)
from ...room.models import Category, Collection, Room, RoomType, RoomVariant
from ...search.backends import picker
from ...hotel.models import Stock
from ..channel.filters import get_channel_slug_from_filter_data
from ..core.filters import EnumFilter, ListObjectTypeFilter, ObjectTypeFilter
from ..core.types import ChannelFilterInputObjectType, FilterInputObjectType
from ..core.types.common import IntRangeInput, PriceRangeInput
from ..utils import get_nodes, resolve_global_ids_to_primary_keys
from ..utils.filters import filter_fields_containing_value, filter_range_field
from ..hotel import types as hotel_types
from .enums import (
    CollectionPublished,
    RoomTypeConfigurable,
    RoomTypeEnum,
    StockAvailability,
)


def _clean_room_attributes_filter_input(
    filter_value,
) -> Dict[int, List[Optional[int]]]:
    attributes = Attribute.objects.prefetch_related("values")
    attributes_map: Dict[str, int] = {
        attribute.slug: attribute.pk for attribute in attributes
    }
    values_map: Dict[str, Dict[str, int]] = {
        attr.slug: {value.slug: value.pk for value in attr.values.all()}
        for attr in attributes
    }
    queries: Dict[int, List[Optional[int]]] = defaultdict(list)
    # Convert attribute:value pairs into a dictionary where
    # attributes are keys and values are grouped in lists
    for attr_name, val_slugs in filter_value:
        if attr_name not in attributes_map:
            raise ValueError("Unknown attribute name: %r" % (attr_name,))
        attr_pk = attributes_map[attr_name]
        attr_val_pk = [
            values_map[attr_name][val_slug]
            for val_slug in val_slugs
            if val_slug in values_map[attr_name]
        ]
        queries[attr_pk] += attr_val_pk

    return queries


T_ROOM_FILTER_QUERIES = Dict[int, Iterable[int]]


def filter_rooms_by_attributes_values(qs, queries: T_ROOM_FILTER_QUERIES):
    filters = [
        Q(
            Exists(
                AssignedRoomAttribute.objects.filter(
                    room__id=OuterRef("pk"), values__pk__in=values
                )
            )
        )
        | Q(
            Exists(
                AssignedVariantAttribute.objects.filter(
                    variant__room__id=OuterRef("pk"),
                    values__pk__in=values,
                )
            )
        )
        for values in queries.values()
    ]

    return qs.filter(*filters)


def filter_rooms_by_attributes(qs, filter_value):
    queries = _clean_room_attributes_filter_input(filter_value)
    return filter_rooms_by_attributes_values(qs, queries)


def filter_rooms_by_variant_price(qs, channel_slug, price_lte=None, price_gte=None):
    if price_lte:
        qs = qs.filter(
            variants__channel_listings__price_amount__lte=price_lte,
            variants__channel_listings__channel__slug=channel_slug,
        )
    if price_gte:
        qs = qs.filter(
            variants__channel_listings__price_amount__gte=price_gte,
            variants__channel_listings__channel__slug=channel_slug,
        )
    return qs


def filter_rooms_by_minimal_price(
    qs, channel_slug, minimal_price_lte=None, minimal_price_gte=None
):
    if minimal_price_lte:
        qs = qs.filter(
            channel_listings__discounted_price_amount__lte=minimal_price_lte,
            channel_listings__channel__slug=channel_slug,
        )
    if minimal_price_gte:
        qs = qs.filter(
            channel_listings__discounted_price_amount__gte=minimal_price_gte,
            channel_listings__channel__slug=channel_slug,
        )
    return qs


def filter_rooms_by_categories(qs, categories):
    categories = [
        category.get_descendants(include_self=True) for category in categories
    ]
    ids = {category.id for tree in categories for category in tree}
    return qs.filter(category__in=ids)


def filter_rooms_by_collections(qs, collections):
    return qs.filter(collections__in=collections)


def filter_rooms_by_stock_availability(qs, stock_availability):
    total_stock = (
        Stock.objects.select_related("room_variant")
        .values("room_variant__room_id")
        .annotate(
            total_quantity_allocated=Coalesce(Sum("allocations__quantity_allocated"), 0)
        )
        .annotate(total_quantity=Coalesce(Sum("quantity"), 0))
        .annotate(total_available=F("total_quantity") - F("total_quantity_allocated"))
        .filter(total_available__lte=0)
        .values_list("room_variant__room_id", flat=True)
    )
    if stock_availability == StockAvailability.IN_STOCK:
        qs = qs.exclude(id__in=Subquery(total_stock))
    elif stock_availability == StockAvailability.OUT_OF_STOCK:
        qs = qs.filter(id__in=Subquery(total_stock))
    return qs


def filter_attributes(qs, _, value):
    if value:
        value_list = []
        for v in value:
            slug = v["slug"]
            values = [v["value"]] if "value" in v else v.get("values", [])
            value_list.append((slug, values))
        qs = filter_rooms_by_attributes(qs, value_list)
    return qs


def filter_categories(qs, _, value):
    if value:
        categories = get_nodes(value, "Category", Category)
        qs = filter_rooms_by_categories(qs, categories)
    return qs


def filter_has_category(qs, _, value):
    return qs.filter(category__isnull=not value)


def filter_collections(qs, _, value):
    if value:
        collections = get_nodes(value, "Collection", Collection)
        qs = filter_rooms_by_collections(qs, collections)
    return qs


def _filter_is_published(qs, _, value, channel_slug):
    return qs.filter(
        channel_listings__is_published=value,
        channel_listings__channel__slug=channel_slug,
    )


def _filter_variant_price(qs, _, value, channel_slug):
    qs = filter_rooms_by_variant_price(
        qs, channel_slug, price_lte=value.get("lte"), price_gte=value.get("gte")
    )
    return qs


def _filter_minimal_price(qs, _, value, channel_slug):
    qs = filter_rooms_by_minimal_price(
        qs,
        channel_slug,
        minimal_price_lte=value.get("lte"),
        minimal_price_gte=value.get("gte"),
    )
    return qs


def filter_stock_availability(qs, _, value):
    if value:
        qs = filter_rooms_by_stock_availability(qs, value)
    return qs


def filter_search(qs, _, value):
    if value:
        search = picker.pick_backend()
        qs = qs.distinct() & search(value).distinct()
    return qs


def filter_room_type_configurable(qs, _, value):
    if value == RoomTypeConfigurable.CONFIGURABLE:
        qs = qs.filter(has_variants=True)
    elif value == RoomTypeConfigurable.SIMPLE:
        qs = qs.filter(has_variants=False)
    return qs


def filter_room_type(qs, _, value):
    if value == RoomTypeEnum.DIGITAL:
        qs = qs.filter(is_digital=True)
    elif value == RoomTypeEnum.SHIPPABLE:
        qs = qs.filter(is_shipping_required=True)
    return qs


def filter_stocks(qs, _, value):
    hotel_ids = value.get("hotel_ids")
    quantity = value.get("quantity")
    if hotel_ids and not quantity:
        return filter_hotels(qs, _, hotel_ids)
    if quantity and not hotel_ids:
        return filter_quantity(qs, quantity)
    if quantity and hotel_ids:
        return filter_quantity(qs, quantity, hotel_ids)
    return qs


def filter_hotels(qs, _, value):
    if value:
        _, hotel_pks = resolve_global_ids_to_primary_keys(
            value, hotel_types.Hotel
        )
        return qs.filter(variants__stocks__hotel__pk__in=hotel_pks)
    return qs


def filter_sku_list(qs, _, value):
    return qs.filter(sku__in=value)


def filter_quantity(qs, quantity_value, hotels=None):
    """Filter rooms queryset by room variants quantity.

    Return room queryset which contains at least one variant with aggregated quantity
    between given range. If hotels is given, it aggregates quantity only
    from stocks which are in given hotels.
    """
    room_variants = RoomVariant.objects.filter(room__in=qs)
    if hotels:
        _, hotel_pks = resolve_global_ids_to_primary_keys(
            hotels, hotel_types.Hotel
        )
        room_variants = room_variants.annotate(
            total_quantity=Sum(
                "stocks__quantity", filter=Q(stocks__hotel__pk__in=hotel_pks)
            )
        )
    else:
        room_variants = room_variants.annotate(
            total_quantity=Sum("stocks__quantity")
        )

    room_variants = filter_range_field(
        room_variants, "total_quantity", quantity_value
    )
    return qs.filter(variants__in=room_variants)


class RoomStockFilterInput(graphene.InputObjectType):
    hotel_ids = graphene.List(graphene.NonNull(graphene.ID), required=False)
    quantity = graphene.Field(IntRangeInput, required=False)


class RoomFilter(django_filters.FilterSet):
    is_published = django_filters.BooleanFilter(method="filter_is_published")
    collections = GlobalIDMultipleChoiceFilter(method=filter_collections)
    categories = GlobalIDMultipleChoiceFilter(method=filter_categories)
    has_category = django_filters.BooleanFilter(method=filter_has_category)
    price = ObjectTypeFilter(input_class=PriceRangeInput, method="filter_variant_price")
    minimal_price = ObjectTypeFilter(
        input_class=PriceRangeInput,
        method="filter_minimal_price",
        field_name="minimal_price_amount",
    )
    attributes = ListObjectTypeFilter(
        input_class="saleor.graphql.attribute.types.AttributeInput",
        method=filter_attributes,
    )
    stock_availability = EnumFilter(
        input_class=StockAvailability, method=filter_stock_availability
    )
    room_type = GlobalIDFilter()  # Deprecated
    room_types = GlobalIDMultipleChoiceFilter(field_name="room_type")
    stocks = ObjectTypeFilter(input_class=RoomStockFilterInput, method=filter_stocks)
    search = django_filters.CharFilter(method=filter_search)
    ids = GlobalIDMultipleChoiceFilter(field_name="id")

    class Meta:
        model = Room
        fields = [
            "is_published",
            "collections",
            "categories",
            "has_category",
            "attributes",
            "stock_availability",
            "room_type",
            "stocks",
            "search",
        ]

    def filter_variant_price(self, queryset, name, value):
        channel_slug = get_channel_slug_from_filter_data(self.data)
        return _filter_variant_price(queryset, name, value, channel_slug)

    def filter_minimal_price(self, queryset, name, value):
        channel_slug = get_channel_slug_from_filter_data(self.data)
        return _filter_minimal_price(queryset, name, value, channel_slug)

    def filter_is_published(self, queryset, name, value):
        channel_slug = get_channel_slug_from_filter_data(self.data)
        return _filter_is_published(queryset, name, value, channel_slug)


class RoomVariantFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method=filter_fields_containing_value("name", "room__name", "sku")
    )
    sku = ListObjectTypeFilter(input_class=graphene.String, method=filter_sku_list)

    class Meta:
        model = RoomVariant
        fields = ["search", "sku"]


class CollectionFilter(django_filters.FilterSet):
    published = EnumFilter(
        input_class=CollectionPublished, method="filter_is_published"
    )
    search = django_filters.CharFilter(
        method=filter_fields_containing_value("slug", "name")
    )
    ids = GlobalIDMultipleChoiceFilter(field_name="id")

    class Meta:
        model = Collection
        fields = ["published", "search"]

    def filter_is_published(self, queryset, name, value):
        channel_slug = get_channel_slug_from_filter_data(self.data)
        if value == CollectionPublished.PUBLISHED:
            return _filter_is_published(queryset, name, True, channel_slug)
        elif value == CollectionPublished.HIDDEN:
            return _filter_is_published(queryset, name, False, channel_slug)
        return queryset


class CategoryFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method=filter_fields_containing_value("slug", "name", "description")
    )
    ids = GlobalIDMultipleChoiceFilter(field_name="id")

    class Meta:
        model = Category
        fields = ["search"]


class RoomTypeFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method=filter_fields_containing_value("name", "slug")
    )

    configurable = EnumFilter(
        input_class=RoomTypeConfigurable, method=filter_room_type_configurable
    )

    room_type = EnumFilter(input_class=RoomTypeEnum, method=filter_room_type)
    ids = GlobalIDMultipleChoiceFilter(field_name="id")

    class Meta:
        model = RoomType
        fields = ["search", "configurable", "room_type"]


class RoomFilterInput(ChannelFilterInputObjectType):
    class Meta:
        filterset_class = RoomFilter


class RoomVariantFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RoomVariantFilter


class CollectionFilterInput(ChannelFilterInputObjectType):
    class Meta:
        filterset_class = CollectionFilter


class CategoryFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CategoryFilter


class RoomTypeFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = RoomTypeFilter
