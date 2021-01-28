from collections import defaultdict
from typing import TYPE_CHECKING, Dict, List

import graphene
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError

from ...hotel.models import Stock

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from ...room.models import RoomVariant


def get_used_attribute_values_for_variant(variant):
    """Create a dict of attributes values for variant.

    Sample result is:
    {
        "attribute_1_global_id": ["ValueAttr1_1"],
        "attribute_2_global_id": ["ValueAttr2_1"]
    }
    """
    attribute_values = defaultdict(list)
    for assigned_variant_attribute in variant.attributes.all():
        attribute = assigned_variant_attribute.attribute
        attribute_id = graphene.Node.to_global_id("Attribute", attribute.id)
        for attr_value in assigned_variant_attribute.values.all():
            attribute_values[attribute_id].append(attr_value.slug)
    return attribute_values


def get_used_variants_attribute_values(room):
    """Create list of attributes values for all existing `RoomVariants` for room.

    Sample result is:
    [
        {
            "attribute_1_global_id": ["ValueAttr1_1"],
            "attribute_2_global_id": ["ValueAttr2_1"]
        },
        ...
        {
            "attribute_1_global_id": ["ValueAttr1_2"],
            "attribute_2_global_id": ["ValueAttr2_2"]
        }
    ]
    """
    variants = (
        room.variants.prefetch_related("attributes__values")
        .prefetch_related("attributes__assignment")
        .all()
    )
    used_attribute_values = []
    for variant in variants:
        attribute_values = get_used_attribute_values_for_variant(variant)
        used_attribute_values.append(attribute_values)
    return used_attribute_values


@transaction.atomic
def create_stocks(
    variant: "RoomVariant", stocks_data: List[Dict[str, str]], hotels: "QuerySet"
):
    try:
        Stock.objects.bulk_create(
            [
                Stock(
                    room_variant=variant,
                    hotel=hotel,
                    quantity=stock_data["quantity"],
                )
                for stock_data, hotel in zip(stocks_data, hotels)
            ]
        )
    except IntegrityError:
        msg = "Stock for one of hotels already exists for this room variant."
        raise ValidationError(msg)