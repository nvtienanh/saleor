from unittest.mock import patch

import graphene
import pytest
from django.utils import timezone
from prices import Money, TaxedMoney

from ....order import OrderStatus
from ....order.models import OrderLine
from ....room.models import (
    Category,
    Collection,
    Room,
    RoomChannelListing,
    RoomImage,
    RoomType,
    RoomVariant,
    RoomVariantChannelListing,
)
from ...tests.utils import get_graphql_content


@pytest.fixture
def category_list():
    category_1 = Category.objects.create(name="Category 1", slug="category-1")
    category_2 = Category.objects.create(name="Category 2", slug="category-2")
    category_3 = Category.objects.create(name="Category 3", slug="category-3")
    return category_1, category_2, category_3


@pytest.fixture
def room_type_list():
    room_type_1 = RoomType.objects.create(name="Type 1", slug="type-1")
    room_type_2 = RoomType.objects.create(name="Type 2", slug="type-2")
    room_type_3 = RoomType.objects.create(name="Type 3", slug="type-3")
    return room_type_1, room_type_2, room_type_3


MUTATION_CATEGORY_BULK_DELETE = """
    mutation categoryBulkDelete($ids: [ID]!) {
        categoryBulkDelete(ids: $ids) {
            count
        }
    }
"""


def test_delete_categories(staff_api_client, category_list, permission_manage_rooms):
    variables = {
        "ids": [
            graphene.Node.to_global_id("Category", category.id)
            for category in category_list
        ]
    }
    response = staff_api_client.post_graphql(
        MUTATION_CATEGORY_BULK_DELETE,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)

    assert content["data"]["categoryBulkDelete"]["count"] == 3
    assert not Category.objects.filter(
        id__in=[category.id for category in category_list]
    ).exists()


@patch("vanphong.room.utils.update_rooms_discounted_prices_task")
def test_delete_categories_with_subcategories_and_rooms(
    mock_update_rooms_discounted_prices_task,
    staff_api_client,
    category_list,
    permission_manage_rooms,
    room,
    category,
    channel_USD,
    channel_PLN,
):
    room.category = category
    category.parent = category_list[0]
    category.save()

    parent_room = Room.objects.get(pk=room.pk)
    parent_room.slug = "parent-room"
    parent_room.id = None
    parent_room.category = category_list[0]
    parent_room.save()

    RoomChannelListing.objects.bulk_create(
        [
            RoomChannelListing(
                room=parent_room, channel=channel_USD, is_published=True
            ),
            RoomChannelListing(
                room=parent_room,
                channel=channel_PLN,
                is_published=True,
                publication_date=timezone.now(),
            ),
        ]
    )

    room_list = [room, parent_room]

    variables = {
        "ids": [
            graphene.Node.to_global_id("Category", category.id)
            for category in category_list
        ]
    }
    response = staff_api_client.post_graphql(
        MUTATION_CATEGORY_BULK_DELETE,
        variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)

    assert content["data"]["categoryBulkDelete"]["count"] == 3
    assert not Category.objects.filter(
        id__in=[category.id for category in category_list]
    ).exists()

    mock_update_rooms_discounted_prices_task.delay.assert_called_once()
    (
        _call_args,
        call_kwargs,
    ) = mock_update_rooms_discounted_prices_task.delay.call_args

    assert set(call_kwargs["room_ids"]) == set([p.pk for p in room_list])

    for room in room_list:
        room.refresh_from_db()
        assert not room.category

    room_channel_listings = RoomChannelListing.objects.filter(
        room__in=room_list
    )
    for room_channel_listing in room_channel_listings:
        assert room_channel_listing.is_published is False
        assert not room_channel_listing.publication_date
    assert room_channel_listings.count() == 3


def test_delete_collections(
    staff_api_client, collection_list, permission_manage_rooms
):
    query = """
    mutation collectionBulkDelete($ids: [ID]!) {
        collectionBulkDelete(ids: $ids) {
            count
        }
    }
    """

    variables = {
        "ids": [
            graphene.Node.to_global_id("Collection", collection.id)
            for collection in collection_list
        ]
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)

    assert content["data"]["collectionBulkDelete"]["count"] == 3
    assert not Collection.objects.filter(
        id__in=[collection.id for collection in collection_list]
    ).exists()


DELETE_ROOMS_MUTATION = """
mutation roomBulkDelete($ids: [ID]!) {
    roomBulkDelete(ids: $ids) {
        count
    }
}
"""


def test_delete_rooms(
    staff_api_client, room_list, permission_manage_rooms, order_list, channel_USD
):
    # given
    query = DELETE_ROOMS_MUTATION

    not_draft_order = order_list[0]
    draft_order = order_list[1]
    draft_order.status = OrderStatus.DRAFT
    draft_order.save(update_fields=["status"])

    draft_order_lines_pks = []
    not_draft_order_lines_pks = []
    for variant in [room_list[0].variants.first(), room_list[1].variants.first()]:
        room = variant.room
        variant_channel_listing = variant.channel_listings.get(channel=channel_USD)
        net = variant.get_price(room, [], channel_USD, variant_channel_listing, None)
        gross = Money(amount=net.amount, currency=net.currency)
        quantity = 3
        total_price = TaxedMoney(net=net * quantity, gross=gross * quantity)
        order_line = OrderLine.objects.create(
            variant=variant,
            order=draft_order,
            room_name=str(room),
            variant_name=str(variant),
            room_sku=variant.sku,
            is_shipping_required=variant.is_shipping_required(),
            unit_price=TaxedMoney(net=net, gross=gross),
            total_price=total_price,
            quantity=3,
        )
        draft_order_lines_pks.append(order_line.pk)

        order_line_not_draft = OrderLine.objects.create(
            variant=variant,
            order=not_draft_order,
            room_name=str(room),
            variant_name=str(variant),
            room_sku=variant.sku,
            is_shipping_required=variant.is_shipping_required(),
            unit_price=TaxedMoney(net=net, gross=gross),
            total_price=total_price,
            quantity=3,
        )
        not_draft_order_lines_pks.append(order_line_not_draft.pk)

    variables = {
        "ids": [
            graphene.Node.to_global_id("Room", room.id)
            for room in room_list
        ]
    }

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    # then
    content = get_graphql_content(response)

    assert content["data"]["roomBulkDelete"]["count"] == 3
    assert not Room.objects.filter(
        id__in=[room.id for room in room_list]
    ).exists()

    assert not OrderLine.objects.filter(pk__in=draft_order_lines_pks).exists()

    assert OrderLine.objects.filter(pk__in=not_draft_order_lines_pks).exists()


def test_delete_rooms_variants_in_draft_order(
    staff_api_client, room_list, permission_manage_rooms
):
    query = DELETE_ROOMS_MUTATION

    assert RoomChannelListing.objects.filter(
        room_id__in=[room.id for room in room_list]
    ).exists()

    variables = {
        "ids": [
            graphene.Node.to_global_id("Room", room.id)
            for room in room_list
        ]
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)

    assert content["data"]["roomBulkDelete"]["count"] == 3
    assert not Room.objects.filter(
        id__in=[room.id for room in room_list]
    ).exists()
    assert not RoomChannelListing.objects.filter(
        room_id__in=[room.id for room in room_list]
    ).exists()


def test_delete_room_images(
    staff_api_client, room_with_images, permission_manage_rooms
):
    images = room_with_images.images.all()

    query = """
    mutation roomImageBulkDelete($ids: [ID]!) {
        roomImageBulkDelete(ids: $ids) {
            count
        }
    }
    """

    variables = {
        "ids": [
            graphene.Node.to_global_id("RoomImage", image.id) for image in images
        ]
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)

    assert content["data"]["roomImageBulkDelete"]["count"] == 2
    assert not RoomImage.objects.filter(
        id__in=[image.id for image in images]
    ).exists()


def test_delete_room_types(
    staff_api_client, room_type_list, permission_manage_room_types_and_attributes
):
    query = """
    mutation roomTypeBulkDelete($ids: [ID]!) {
        roomTypeBulkDelete(ids: $ids) {
            count
        }
    }
    """

    variables = {
        "ids": [
            graphene.Node.to_global_id("RoomType", type.id)
            for type in room_type_list
        ]
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_room_types_and_attributes]
    )
    content = get_graphql_content(response)

    assert content["data"]["roomTypeBulkDelete"]["count"] == 3
    assert not RoomType.objects.filter(
        id__in=[type.id for type in room_type_list]
    ).exists()


ROOM_VARIANT_BULK_DELETE_MUTATION = """
mutation roomVariantBulkDelete($ids: [ID]!) {
    roomVariantBulkDelete(ids: $ids) {
        count
    }
}
"""


def test_delete_room_variants(
    staff_api_client, room_variant_list, permission_manage_rooms
):
    query = ROOM_VARIANT_BULK_DELETE_MUTATION

    assert RoomVariantChannelListing.objects.filter(
        variant_id__in=[variant.id for variant in room_variant_list]
    ).exists()

    variables = {
        "ids": [
            graphene.Node.to_global_id("RoomVariant", variant.id)
            for variant in room_variant_list
        ]
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)

    assert content["data"]["roomVariantBulkDelete"]["count"] == 3
    assert not RoomVariant.objects.filter(
        id__in=[variant.id for variant in room_variant_list]
    ).exists()


def test_delete_room_variants_in_draft_orders(
    staff_api_client,
    room_variant_list,
    permission_manage_rooms,
    order_line,
    order_list,
    channel_USD,
):
    # given
    query = ROOM_VARIANT_BULK_DELETE_MUTATION
    variants = room_variant_list

    draft_order = order_line.order
    draft_order.status = OrderStatus.DRAFT
    draft_order.save(update_fields=["status"])

    second_variant_in_draft = variants[1]
    second_room = second_variant_in_draft.room
    second_variant_channel_listing = second_variant_in_draft.channel_listings.get(
        channel=channel_USD
    )
    net = second_variant_in_draft.get_price(
        second_room, [], channel_USD, second_variant_channel_listing, None
    )
    gross = Money(amount=net.amount, currency=net.currency)
    unit_price = TaxedMoney(net=net, gross=gross)
    quantity = 3
    total_price = unit_price * quantity
    second_draft_order = OrderLine.objects.create(
        variant=second_variant_in_draft,
        order=draft_order,
        room_name=str(second_room),
        variant_name=str(second_variant_in_draft),
        room_sku=second_variant_in_draft.sku,
        is_shipping_required=second_variant_in_draft.is_shipping_required(),
        unit_price=TaxedMoney(net=net, gross=gross),
        total_price=total_price,
        quantity=quantity,
    )

    variant = variants[0]
    room = variant.room
    variant_channel_listing = variant.channel_listings.get(channel=channel_USD)
    net = variant.get_price(room, [], channel_USD, variant_channel_listing, None)
    gross = Money(amount=net.amount, currency=net.currency)
    unit_price = TaxedMoney(net=net, gross=gross)
    quantity = 3
    total_price = unit_price * quantity
    order_not_draft = order_list[-1]
    order_line_not_in_draft = OrderLine.objects.create(
        variant=variant,
        order=order_not_draft,
        room_name=str(room),
        variant_name=str(variant),
        room_sku=variant.sku,
        is_shipping_required=variant.is_shipping_required(),
        unit_price=TaxedMoney(net=net, gross=gross),
        total_price=total_price,
        quantity=quantity,
    )
    order_line_not_in_draft_pk = order_line_not_in_draft.pk

    variant_count = RoomVariant.objects.count()

    variables = {
        "ids": [
            graphene.Node.to_global_id("RoomVariant", variant.id)
            for variant in RoomVariant.objects.all()
        ]
    }

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    # then
    content = get_graphql_content(response)

    assert content["data"]["roomVariantBulkDelete"]["count"] == variant_count
    assert not RoomVariant.objects.filter(
        id__in=[variant.id for variant in room_variant_list]
    ).exists()

    with pytest.raises(order_line._meta.model.DoesNotExist):
        order_line.refresh_from_db()

    with pytest.raises(second_draft_order._meta.model.DoesNotExist):
        second_draft_order.refresh_from_db()

    assert OrderLine.objects.filter(pk=order_line_not_in_draft_pk).exists()


def test_delete_room_variants_delete_default_variant(
    staff_api_client, room, permission_manage_rooms
):
    # given
    query = ROOM_VARIANT_BULK_DELETE_MUTATION

    new_default_variant = room.variants.first()

    variants = RoomVariant.objects.bulk_create(
        [
            RoomVariant(room=room, sku="1"),
            RoomVariant(room=room, sku="2"),
            RoomVariant(room=room, sku="3"),
        ]
    )

    default_variant = variants[0]

    room = default_variant.room
    room.default_variant = default_variant
    room.save(update_fields=["default_variant"])

    variables = {
        "ids": [
            graphene.Node.to_global_id("RoomVariant", variant.id)
            for variant in variants
        ]
    }

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    # then
    content = get_graphql_content(response)

    assert content["data"]["roomVariantBulkDelete"]["count"] == 3
    assert not RoomVariant.objects.filter(
        id__in=[variant.id for variant in variants]
    ).exists()

    room.refresh_from_db()
    assert room.default_variant.pk == new_default_variant.pk


def test_delete_room_variants_delete_all_room_variants(
    staff_api_client, room, permission_manage_rooms
):
    # given
    query = ROOM_VARIANT_BULK_DELETE_MUTATION

    new_default_variant = room.variants.first()

    variants = RoomVariant.objects.bulk_create(
        [
            RoomVariant(room=room, sku="1"),
            RoomVariant(room=room, sku="2"),
        ]
    )

    default_variant = variants[0]

    room = default_variant.room
    room.default_variant = default_variant
    room.save(update_fields=["default_variant"])

    ids = [
        graphene.Node.to_global_id("RoomVariant", variant.id) for variant in variants
    ]
    ids.append(graphene.Node.to_global_id("RoomVariant", new_default_variant.id))

    variables = {"ids": ids}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    # then
    content = get_graphql_content(response)

    assert content["data"]["roomVariantBulkDelete"]["count"] == 3
    assert not RoomVariant.objects.filter(
        id__in=[variant.id for variant in variants]
    ).exists()

    room.refresh_from_db()
    assert room.default_variant is None


def test_delete_room_variants_from_different_rooms(
    staff_api_client, room, room_with_two_variants, permission_manage_rooms
):
    # given
    query = ROOM_VARIANT_BULK_DELETE_MUTATION

    room_1 = room
    room_2 = room_with_two_variants

    room_1_default_variant = room_1.variants.first()
    room_2_default_variant = room_2.variants.first()

    room_1.default_variant = room_1_default_variant
    room_2.default_variant = room_2_default_variant

    Room.objects.bulk_update([room_1, room_2], ["default_variant"])

    room_2_second_variant = room_2.variants.last()

    variables = {
        "ids": [
            graphene.Node.to_global_id("RoomVariant", room_1_default_variant.id),
            graphene.Node.to_global_id("RoomVariant", room_2_default_variant.id),
        ]
    }

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )

    # then
    content = get_graphql_content(response)

    assert content["data"]["roomVariantBulkDelete"]["count"] == 2
    assert not RoomVariant.objects.filter(
        id__in=[room_1_default_variant.id, room_2_default_variant.id]
    ).exists()

    room_1.refresh_from_db()
    room_2.refresh_from_db()

    assert room_1.default_variant is None
    assert room_2.default_variant.pk == room_2_second_variant.pk
