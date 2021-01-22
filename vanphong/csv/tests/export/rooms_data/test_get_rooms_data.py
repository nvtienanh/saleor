from measurement.measures import Weight

from .....attribute.models import Attribute, AttributeValue
from .....attribute.utils import associate_attribute_values_to_instance
from .....channel.models import Channel
from .....room.models import Room, RoomVariant, VariantImage
from .....hotel.models import Hotel
from ....utils import RoomExportFields
from ....utils.rooms_data import get_rooms_data
from .utils import (
    add_channel_to_expected_room_data,
    add_channel_to_expected_variant_data,
    add_room_attribute_data_to_expected_data,
    add_stocks_to_expected_data,
    add_variant_attribute_data_to_expected_data,
)


def test_get_rooms_data(room, room_with_image, collection, image, channel_USD):
    # given
    room.weight = Weight(kg=5)
    room.save()

    collection.rooms.add(room)

    variant = room.variants.first()
    VariantImage.objects.create(variant=variant, image=room.images.first())

    rooms = Room.objects.all()
    export_fields = set(
        value
        for mapping in RoomExportFields.HEADERS_TO_FIELDS_MAPPING.values()
        for value in mapping.values()
    )
    hotel_ids = [str(hotel.pk) for hotel in Hotel.objects.all()]
    attribute_ids = [str(attr.pk) for attr in Attribute.objects.all()]
    channel_ids = [str(channel.pk) for channel in Channel.objects.all()]

    variants = []
    for variant in room.variants.all():
        for attr in variant.attributes.all():
            attribute_ids.append(str(attr.assignment.attribute.pk))
        variant.weight = Weight(kg=3)
        variants.append(variant)

    RoomVariant.objects.bulk_update(variants, ["weight"])

    variants = []
    for variant in room_with_image.variants.all():
        variant.weight = None
        variants.append(variant)
    RoomVariant.objects.bulk_update(variants, ["weight"])

    # when
    result_data = get_rooms_data(
        rooms, export_fields, attribute_ids, hotel_ids, channel_ids
    )

    # then
    expected_data = []
    for room in rooms.order_by("pk"):
        room_data = {
            "id": room.id,
            "name": room.name,
            "description": room.description,
            "category__slug": room.category.slug,
            "room_type__name": room.room_type.name,
            "charge_taxes": room.charge_taxes,
            "collections__slug": (
                ""
                if not room.collections.all()
                else room.collections.first().slug
            ),
            "room_weight": (
                "{} g".format(int(room.weight.value * 1000))
                if room.weight
                else ""
            ),
            "images__image": (
                ""
                if not room.images.all()
                else "http://mirumee.com{}".format(room.images.first().image.url)
            ),
        }

        room_data = add_room_attribute_data_to_expected_data(
            room_data, room, attribute_ids
        )
        room_data = add_channel_to_expected_room_data(
            room_data, room, channel_ids
        )

        for variant in room.variants.all():
            data = {
                "variants__sku": variant.sku,
                "variants__images__image": (
                    ""
                    if not variant.images.all()
                    else "http://mirumee.com{}".format(variant.images.first().image.url)
                ),
                "variant_weight": (
                    "{} g".foramt(int(variant.weight.value * 1000))
                    if variant.weight
                    else ""
                ),
            }
            data.update(room_data)

            data = add_stocks_to_expected_data(data, variant, hotel_ids)
            data = add_variant_attribute_data_to_expected_data(
                data, variant, attribute_ids
            )
            data = add_channel_to_expected_variant_data(data, variant, channel_ids)

            expected_data.append(data)
    assert result_data == expected_data


def test_get_rooms_data_for_specified_attributes(
    room, room_with_variant_with_two_attributes
):
    # given
    rooms = Room.objects.all()
    export_fields = {"id", "variants__sku"}
    attribute_ids = [str(attr.pk) for attr in Attribute.objects.all()][:1]
    hotel_ids = []
    channel_ids = []

    # when
    result_data = get_rooms_data(
        rooms, export_fields, attribute_ids, hotel_ids, channel_ids
    )

    # then
    expected_data = []
    for room in rooms.order_by("pk"):
        room_data = {"id": room.pk}

        room_data = add_room_attribute_data_to_expected_data(
            room_data, room, attribute_ids
        )

        for variant in room.variants.all():
            data = {}
            data.update(room_data)
            data["variants__sku"] = variant.sku
            data = add_variant_attribute_data_to_expected_data(
                data, variant, attribute_ids
            )

            expected_data.append(data)

    assert result_data == expected_data


def test_get_rooms_data_for_specified_hotels(
    room, room_with_image, variant_with_many_stocks
):
    # given
    room.variants.add(variant_with_many_stocks)

    rooms = Room.objects.all()
    export_fields = {"id", "variants__sku"}
    hotel_ids = [str(hotel.pk) for hotel in Hotel.objects.all()][:2]
    attribute_ids = []
    channel_ids = []

    # when
    result_data = get_rooms_data(
        rooms, export_fields, attribute_ids, hotel_ids, channel_ids
    )

    # then
    expected_data = []
    for room in rooms.order_by("pk"):
        room_data = {"id": room.pk}

        for variant in room.variants.all():
            data = {"variants__sku": variant.sku}
            data.update(room_data)

            data = add_stocks_to_expected_data(data, variant, hotel_ids)

            expected_data.append(data)
    for res in result_data:
        assert res in expected_data


def test_get_rooms_data_for_room_without_channel(
    room, room_with_image, variant_with_many_stocks
):
    # given
    room.variants.add(variant_with_many_stocks)
    room_with_image.channel_listings.all().delete()

    rooms = Room.objects.all()
    export_fields = {"id", "variants__sku"}
    hotel_ids = []
    attribute_ids = []
    channel_ids = []

    # when
    result_data = get_rooms_data(
        rooms, export_fields, attribute_ids, hotel_ids, channel_ids
    )

    # then
    expected_data = []
    for room in rooms.order_by("pk"):
        room_data = {"id": room.pk}

        for variant in room.variants.all():
            data = {"variants__sku": variant.sku}
            data.update(room_data)

            data = add_stocks_to_expected_data(data, variant, hotel_ids)

            expected_data.append(data)

    for res in result_data:
        assert res in expected_data


def test_get_rooms_data_for_specified_hotels_channels_and_attributes(
    room,
    variant_with_many_stocks,
    room_with_image,
    room_with_variant_with_two_attributes,
    file_attribute,
    room_type_page_reference_attribute,
    room_type_room_reference_attribute,
    page_list,
):
    # given
    room.variants.add(variant_with_many_stocks)
    room.room_type.variant_attributes.add(
        file_attribute,
        room_type_page_reference_attribute,
        room_type_room_reference_attribute,
    )
    room.room_type.room_attributes.add(
        file_attribute,
        room_type_page_reference_attribute,
        room_type_room_reference_attribute,
    )

    # add file attribute
    associate_attribute_values_to_instance(
        variant_with_many_stocks, file_attribute, file_attribute.values.first()
    )
    associate_attribute_values_to_instance(
        room, file_attribute, file_attribute.values.first()
    )

    # add page reference attribute
    room_page_ref_value = AttributeValue.objects.create(
        attribute=room_type_page_reference_attribute,
        slug=f"{room.pk}_{page_list[0].pk}",
        name=page_list[0].title,
    )
    variant_page_ref_value = AttributeValue.objects.create(
        attribute=room_type_page_reference_attribute,
        slug=f"{variant_with_many_stocks.pk}_{page_list[1].pk}",
        name=page_list[1].title,
    )
    associate_attribute_values_to_instance(
        variant_with_many_stocks,
        room_type_page_reference_attribute,
        variant_page_ref_value,
    )
    associate_attribute_values_to_instance(
        room, room_type_page_reference_attribute, room_page_ref_value
    )

    # add room reference attribute
    variant_room_ref_value = AttributeValue.objects.create(
        attribute=room_type_room_reference_attribute,
        slug=(
            f"{variant_with_many_stocks.pk}"
            f"_{room_with_variant_with_two_attributes.pk}"
        ),
        name=room_with_variant_with_two_attributes.name,
    )
    room_room_ref_value = AttributeValue.objects.create(
        attribute=room_type_room_reference_attribute,
        slug=f"{room.pk}_{room_with_image.pk}",
        name=room_with_image.name,
    )
    associate_attribute_values_to_instance(
        variant_with_many_stocks,
        room_type_room_reference_attribute,
        variant_room_ref_value,
    )
    associate_attribute_values_to_instance(
        room, room_type_room_reference_attribute, room_room_ref_value
    )

    rooms = Room.objects.all()
    export_fields = {"id", "variants__sku"}
    hotel_ids = [str(hotel.pk) for hotel in Hotel.objects.all()]
    attribute_ids = [str(attr.pk) for attr in Attribute.objects.all()]
    channel_ids = [str(channel.pk) for channel in Channel.objects.all()]

    # when
    result_data = get_rooms_data(
        rooms, export_fields, attribute_ids, hotel_ids, channel_ids
    )

    # then
    expected_data = []
    for room in rooms.order_by("pk"):
        room_data = {"id": room.id}

        room_data = add_room_attribute_data_to_expected_data(
            room_data, room, attribute_ids
        )
        room_data = add_channel_to_expected_room_data(
            room_data, room, channel_ids
        )

        for variant in room.variants.all():
            data = {"variants__sku": variant.sku}
            data.update(room_data)

            data = add_stocks_to_expected_data(data, variant, hotel_ids)
            data = add_variant_attribute_data_to_expected_data(
                data, variant, attribute_ids
            )
            data = add_channel_to_expected_variant_data(data, variant, channel_ids)

            expected_data.append(data)

    assert result_data == expected_data
