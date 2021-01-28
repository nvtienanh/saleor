from unittest.mock import patch

import pytest

from ...core.exceptions import InsufficientStock
from ...hotel.models import Allocation, Stock
from ..actions import create_fulfillments
from ..models import FulfillmentLine, OrderStatus


@patch("vanphong.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments(
    mock_email_fulfillment,
    staff_user,
    order_with_lines,
    hotel,
):
    order = order_with_lines
    order_line1, order_line2 = order.lines.all()
    fulfillment_lines_for_hotels = {
        str(hotel.pk): [
            {"order_line": order_line1, "quantity": 3},
            {"order_line": order_line2, "quantity": 2},
        ]
    }

    [fulfillment] = create_fulfillments(
        staff_user, order, fulfillment_lines_for_hotels, True
    )

    order.refresh_from_db()
    fulfillment_lines = FulfillmentLine.objects.filter(
        fulfillment__order=order
    ).order_by("pk")
    assert fulfillment_lines[0].stock == order_line1.variant.stocks.get()
    assert fulfillment_lines[0].quantity == 3
    assert fulfillment_lines[1].stock == order_line2.variant.stocks.get()
    assert fulfillment_lines[1].quantity == 2

    assert order.status == OrderStatus.FULFILLED
    assert order.fulfillments.get() == fulfillment

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 3
    assert order_line2.quantity_fulfilled == 2

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 0
    )

    mock_email_fulfillment.assert_called_once_with(
        order, order.fulfillments.get(), staff_user
    )


@patch("vanphong.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_without_notification(
    mock_email_fulfillment,
    staff_user,
    order_with_lines,
    hotel,
):
    order = order_with_lines
    order_line1, order_line2 = order.lines.all()
    fulfillment_lines_for_hotels = {
        str(hotel.pk): [
            {"order_line": order_line1, "quantity": 3},
            {"order_line": order_line2, "quantity": 2},
        ]
    }

    [fulfillment] = create_fulfillments(
        staff_user, order, fulfillment_lines_for_hotels, False
    )

    order.refresh_from_db()
    fulfillment_lines = FulfillmentLine.objects.filter(
        fulfillment__order=order
    ).order_by("pk")
    assert fulfillment_lines[0].stock == order_line1.variant.stocks.get()
    assert fulfillment_lines[0].quantity == 3
    assert fulfillment_lines[1].stock == order_line2.variant.stocks.get()
    assert fulfillment_lines[1].quantity == 2

    assert order.status == OrderStatus.FULFILLED
    assert order.fulfillments.get() == fulfillment

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 3
    assert order_line2.quantity_fulfilled == 2

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 0
    )

    mock_email_fulfillment.assert_not_called()


def test_create_fulfillments_many_hotels(
    staff_user,
    order_with_lines,
    hotels,
):
    order = order_with_lines
    hotel1, hotel2 = hotels
    order_line1, order_line2 = order.lines.all()

    stock_w1_l1 = Stock(
        hotel=hotel1, room_variant=order_line1.variant, quantity=3
    )
    stock_w1_l2 = Stock(
        hotel=hotel1, room_variant=order_line2.variant, quantity=1
    )
    stock_w2_l2 = Stock(
        hotel=hotel2, room_variant=order_line2.variant, quantity=1
    )
    Stock.objects.bulk_create([stock_w1_l1, stock_w1_l2, stock_w2_l2])
    fulfillment_lines_for_hotels = {
        str(hotel1.pk): [
            {"order_line": order_line1, "quantity": 3},
            {"order_line": order_line2, "quantity": 1},
        ],
        str(hotel2.pk): [{"order_line": order_line2, "quantity": 1}],
    }

    [fulfillment1, fulfillment2] = create_fulfillments(
        staff_user, order, fulfillment_lines_for_hotels, False
    )

    order.refresh_from_db()
    fulfillment_lines = FulfillmentLine.objects.filter(
        fulfillment__order=order
    ).order_by("pk")
    assert fulfillment_lines[0].stock == stock_w1_l1
    assert fulfillment_lines[0].quantity == 3
    assert fulfillment_lines[1].stock == stock_w1_l2
    assert fulfillment_lines[1].quantity == 1
    assert fulfillment_lines[2].stock == stock_w2_l2
    assert fulfillment_lines[2].quantity == 1

    assert order.status == OrderStatus.FULFILLED
    assert order.fulfillments.get(fulfillment_order=1) == fulfillment1
    assert order.fulfillments.get(fulfillment_order=2) == fulfillment2

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 3
    assert order_line2.quantity_fulfilled == 2

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 0
    )


@patch("vanphong.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_with_one_line_empty_quantity(
    mock_email_fulfillment,
    staff_user,
    order_with_lines,
    hotel,
):
    order = order_with_lines
    order_line1, order_line2 = order.lines.all()
    fulfillment_lines_for_hotels = {
        str(hotel.pk): [
            {"order_line": order_line1, "quantity": 0},
            {"order_line": order_line2, "quantity": 2},
        ]
    }

    [fulfillment] = create_fulfillments(
        staff_user, order, fulfillment_lines_for_hotels, True
    )

    order.refresh_from_db()
    fulfillment_lines = FulfillmentLine.objects.filter(
        fulfillment__order=order
    ).order_by("pk")
    assert fulfillment_lines[0].stock == order_line2.variant.stocks.get()
    assert fulfillment_lines[0].quantity == 2

    assert order.status == OrderStatus.PARTIALLY_FULFILLED
    assert order.fulfillments.get() == fulfillment

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 0
    assert order_line2.quantity_fulfilled == 2

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 1
    )

    mock_email_fulfillment.assert_called_once_with(
        order, order.fulfillments.get(), staff_user
    )


@patch("vanphong.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_with_variant_without_inventory_tracking(
    mock_email_fulfillment,
    staff_user,
    order_with_line_without_inventory_tracking,
    hotel,
):
    order = order_with_line_without_inventory_tracking
    order_line = order.lines.get()
    stock = order_line.variant.stocks.get()
    stock_quantity_before = stock.quantity
    fulfillment_lines_for_hotels = {
        str(hotel.pk): [{"order_line": order_line, "quantity": 2}]
    }

    [fulfillment] = create_fulfillments(
        staff_user, order, fulfillment_lines_for_hotels, True
    )

    order.refresh_from_db()
    fulfillment_lines = FulfillmentLine.objects.filter(
        fulfillment__order=order
    ).order_by("pk")
    assert fulfillment_lines[0].stock == order_line.variant.stocks.get()
    assert fulfillment_lines[0].quantity == 2

    assert order.status == OrderStatus.PARTIALLY_FULFILLED
    assert order.fulfillments.get() == fulfillment

    order_line = order.lines.get()
    assert order_line.quantity_fulfilled == 2

    stock.refresh_from_db()
    assert stock_quantity_before == stock.quantity

    mock_email_fulfillment.assert_called_once_with(
        order, order.fulfillments.get(), staff_user
    )


@patch("vanphong.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_without_allocations(
    mock_email_fulfillment,
    staff_user,
    order_with_lines,
    hotel,
):
    order = order_with_lines
    order_line1, order_line2 = order.lines.all()
    Allocation.objects.filter(order_line__order=order).delete()
    fulfillment_lines_for_hotels = {
        str(hotel.pk): [
            {"order_line": order_line1, "quantity": 3},
            {"order_line": order_line2, "quantity": 2},
        ]
    }

    [fulfillment] = create_fulfillments(
        staff_user, order, fulfillment_lines_for_hotels, True
    )

    order.refresh_from_db()
    fulfillment_lines = FulfillmentLine.objects.filter(
        fulfillment__order=order
    ).order_by("pk")
    assert fulfillment_lines[0].stock == order_line1.variant.stocks.get()
    assert fulfillment_lines[0].quantity == 3
    assert fulfillment_lines[1].stock == order_line2.variant.stocks.get()
    assert fulfillment_lines[1].quantity == 2

    assert order.status == OrderStatus.FULFILLED
    assert order.fulfillments.get() == fulfillment

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 3
    assert order_line2.quantity_fulfilled == 2

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 0
    )

    mock_email_fulfillment.assert_called_once_with(
        order, order.fulfillments.get(), staff_user
    )


@patch("vanphong.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_hotel_with_out_of_stock(
    mock_email_fulfillment,
    staff_user,
    order_with_lines,
    hotel,
):
    order = order_with_lines
    order_line1, order_line2 = order.lines.all()
    order_line1.allocations.all().delete()
    stock = order_line1.variant.stocks.get(hotel=hotel)
    stock.quantity = 2
    stock.save(update_fields=["quantity"])
    fulfillment_lines_for_hotels = {
        str(hotel.pk): [
            {"order_line": order_line1, "quantity": 3},
            {"order_line": order_line2, "quantity": 2},
        ]
    }

    with pytest.raises(InsufficientStock) as exc:
        create_fulfillments(staff_user, order, fulfillment_lines_for_hotels, True)

    assert exc.value.item == order_line1.variant
    assert exc.value.context == {
        "order_line": order_line1,
        "hotel_pk": str(hotel.pk),
    }

    order.refresh_from_db()
    assert FulfillmentLine.objects.filter(fulfillment__order=order).count() == 0

    assert order.status == OrderStatus.UNFULFILLED
    assert order.fulfillments.all().count() == 0

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 0
    assert order_line2.quantity_fulfilled == 0

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 1
    )

    mock_email_fulfillment.assert_not_called()


@patch("vanphong.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_hotel_without_stock(
    mock_email_fulfillment,
    staff_user,
    order_with_lines,
    hotel_no_shipping_zone,
):
    order = order_with_lines
    order_line1, order_line2 = order.lines.all()
    fulfillment_lines_for_hotels = {
        str(hotel_no_shipping_zone.pk): [
            {"order_line": order_line1, "quantity": 3},
            {"order_line": order_line2, "quantity": 2},
        ]
    }

    with pytest.raises(InsufficientStock) as exc:
        create_fulfillments(staff_user, order, fulfillment_lines_for_hotels, True)

    assert exc.value.item == order_line1.variant
    assert exc.value.context == {
        "order_line": order_line1,
        "hotel_pk": str(hotel_no_shipping_zone.pk),
    }

    order.refresh_from_db()
    assert FulfillmentLine.objects.filter(fulfillment__order=order).count() == 0

    assert order.status == OrderStatus.UNFULFILLED
    assert order.fulfillments.all().count() == 0

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 0
    assert order_line2.quantity_fulfilled == 0

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 2
    )

    mock_email_fulfillment.assert_not_called()


@patch("vanphong.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_with_variant_without_inventory_tracking_and_without_stock(
    mock_email_fulfillment,
    staff_user,
    order_with_line_without_inventory_tracking,
    hotel_no_shipping_zone,
):
    order = order_with_line_without_inventory_tracking
    order_line = order.lines.get()
    fulfillment_lines_for_hotels = {
        str(hotel_no_shipping_zone.pk): [{"order_line": order_line, "quantity": 2}]
    }

    with pytest.raises(InsufficientStock) as exc:
        create_fulfillments(staff_user, order, fulfillment_lines_for_hotels, True)

    assert exc.value.item == order_line.variant
    assert exc.value.context == {
        "order_line": order_line,
        "hotel_pk": str(hotel_no_shipping_zone.pk),
    }

    order.refresh_from_db()
    assert FulfillmentLine.objects.filter(fulfillment__order=order).count() == 0

    assert order.status == OrderStatus.UNFULFILLED
    assert order.fulfillments.all().count() == 0

    order_line = order.lines.get()
    assert order_line.quantity_fulfilled == 0

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 0
    )

    mock_email_fulfillment.assert_not_called()