from typing import Iterable, List, Optional

from ..attribute.models import Attribute
from ..celeryconf import app
from ..discount.models import Sale
from .models import Room, RoomType, RoomVariant
from .utils.variant_prices import (
    update_room_discounted_price,
    update_rooms_discounted_prices,
    update_rooms_discounted_prices_of_catalogues,
    update_rooms_discounted_prices_of_discount,
)
from .utils.variants import generate_and_set_variant_name


def _update_variants_names(instance: RoomType, saved_attributes: Iterable):
    """Room variant names are created from names of assigned attributes.

    After change in attribute value name, for all room variants using this
    attributes we need to update the names.
    """
    initial_attributes = set(instance.variant_attributes.all())
    attributes_changed = initial_attributes.intersection(saved_attributes)
    if not attributes_changed:
        return
    variants_to_be_updated = RoomVariant.objects.filter(
        room__in=instance.rooms.all(),
        room__room_type__variant_attributes__in=attributes_changed,
    )
    variants_to_be_updated = variants_to_be_updated.prefetch_related(
        "attributes__values__translations"
    ).all()
    for variant in variants_to_be_updated:
        generate_and_set_variant_name(variant, variant.sku)


@app.task
def update_variants_names(room_type_pk: int, saved_attributes_ids: List[int]):
    instance = RoomType.objects.get(pk=room_type_pk)
    saved_attributes = Attribute.objects.filter(pk__in=saved_attributes_ids)
    _update_variants_names(instance, saved_attributes)


@app.task
def update_room_discounted_price_task(room_pk: int):
    room = Room.objects.get(pk=room_pk)
    update_room_discounted_price(room)


@app.task
def update_rooms_discounted_prices_of_catalogues_task(
    room_ids: Optional[List[int]] = None,
    category_ids: Optional[List[int]] = None,
    collection_ids: Optional[List[int]] = None,
):
    update_rooms_discounted_prices_of_catalogues(
        room_ids, category_ids, collection_ids
    )


@app.task
def update_rooms_discounted_prices_of_discount_task(discount_pk: int):
    discount = Sale.objects.get(pk=discount_pk)
    update_rooms_discounted_prices_of_discount(discount)


@app.task
def update_rooms_discounted_prices_task(room_ids: List[int]):
    rooms = Room.objects.filter(pk__in=room_ids)
    update_rooms_discounted_prices(rooms)
