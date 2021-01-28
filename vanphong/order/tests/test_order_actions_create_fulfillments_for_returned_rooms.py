from decimal import Decimal
from unittest.mock import patch

from prices import Money, TaxedMoney

from ...plugins.manager import get_plugins_manager
from ...tests.utils import flush_post_commit_hooks
from ...hotel.models import Allocation, Stock
from .. import FulfillmentLineData, FulfillmentStatus, OrderEvents, OrderLineData
from ..actions import create_fulfillments_for_returned_rooms
from ..models import Fulfillment, FulfillmentLine


@patch("vanphong.order.actions.gateway.refund")
def test_create_return_fulfillment_only_order_lines(
    mocked_refund, order_with_lines, payment_dummy_fully_charged, staff_user
):
    order_with_lines.payments.add(payment_dummy_fully_charged)
    payment = order_with_lines.get_last_payment()

    order_lines_to_return = order_with_lines.lines.all()
    original_quantity = {
        line.id: line.quantity_unfulfilled for line in order_with_lines
    }
    order_line_ids = order_lines_to_return.values_list("id", flat=True)
    original_allocations = list(
        Allocation.objects.filter(order_line_id__in=order_line_ids)
    )
    lines_count = order_with_lines.lines.count()

    response = create_fulfillments_for_returned_rooms(
        requester=staff_user,
        order=order_with_lines,
        payment=payment,
        order_lines=[
            OrderLineData(line=line, quantity=2, replace=False)
            for line in order_lines_to_return
        ],
        fulfillment_lines=[],
        plugin_manager=get_plugins_manager(),
    )
    returned_fulfillment, replaced_fulfillment, replace_order = response

    returned_fulfillment_lines = returned_fulfillment.lines.all()
    assert returned_fulfillment.status == FulfillmentStatus.RETURNED
    assert len(returned_fulfillment_lines) == lines_count
    for fulfillment_line in returned_fulfillment_lines:
        assert fulfillment_line.quantity == 2
        assert fulfillment_line.order_line_id in order_line_ids
    for line in order_lines_to_return:
        assert line.quantity_unfulfilled == original_quantity.get(line.pk) - 2

    current_allocations = Allocation.objects.in_bulk(
        [allocation.pk for allocation in original_allocations]
    )
    for original_allocation in original_allocations:
        current_allocation = current_allocations.get(original_allocation.pk)
        assert (
            original_allocation.quantity_allocated - 2
            == current_allocation.quantity_allocated
        )
    assert not mocked_refund.called
    assert not replace_order

    # check if we have correct events
    flush_post_commit_hooks()
    events = order_with_lines.events.all()
    assert events.count() == 1
    returned_event = events[0]
    assert returned_event.type == OrderEvents.FULFILLMENT_RETURNED
    assert len(returned_event.parameters["lines"]) == 2
    event_lines = returned_event.parameters["lines"]
    assert order_lines_to_return.filter(id=event_lines[0]["line_pk"]).exists()
    assert event_lines[0]["quantity"] == 2

    assert order_lines_to_return.filter(id=event_lines[1]["line_pk"]).exists()
    assert event_lines[1]["quantity"] == 2


@patch("vanphong.order.actions.gateway.refund")
def test_create_return_fulfillment_only_order_lines_with_refund(
    mocked_refund, order_with_lines, payment_dummy_fully_charged, staff_user
):
    order_with_lines.payments.add(payment_dummy_fully_charged)
    payment = order_with_lines.get_last_payment()

    order_lines_to_return = order_with_lines.lines.all()
    original_quantity = {
        line.id: line.quantity_unfulfilled for line in order_with_lines
    }
    order_line_ids = order_lines_to_return.values_list("id", flat=True)
    original_allocations = list(
        Allocation.objects.filter(order_line_id__in=order_line_ids)
    )
    lines_count = order_with_lines.lines.count()

    response = create_fulfillments_for_returned_rooms(
        requester=staff_user,
        order=order_with_lines,
        payment=payment,
        order_lines=[
            OrderLineData(line=line, quantity=2, replace=False)
            for line in order_lines_to_return
        ],
        fulfillment_lines=[],
        plugin_manager=get_plugins_manager(),
        refund=True,
    )
    returned_fulfillment, replaced_fulfillment, replace_order = response

    returned_fulfillment_lines = returned_fulfillment.lines.all()
    assert returned_fulfillment.status == FulfillmentStatus.REFUNDED_AND_RETURNED
    assert len(returned_fulfillment_lines) == lines_count
    for fulfillment_line in returned_fulfillment_lines:
        assert fulfillment_line.quantity == 2
        assert fulfillment_line.order_line_id in order_line_ids
    for line in order_lines_to_return:
        assert line.quantity_unfulfilled == original_quantity.get(line.pk) - 2

    current_allocations = Allocation.objects.in_bulk(
        [allocation.pk for allocation in original_allocations]
    )
    for original_allocation in original_allocations:
        current_allocation = current_allocations.get(original_allocation.pk)
        assert (
            original_allocation.quantity_allocated - 2
            == current_allocation.quantity_allocated
        )

    amount = sum([line.unit_price_gross_amount * 2 for line in order_lines_to_return])
    mocked_refund.assert_called_once_with(payment_dummy_fully_charged, amount)
    assert not replace_order


@patch("vanphong.order.actions.gateway.refund")
def test_create_return_fulfillment_only_order_lines_included_shipping_costs(
    mocked_refund, order_with_lines, payment_dummy_fully_charged, staff_user
):
    order_with_lines.payments.add(payment_dummy_fully_charged)
    payment = order_with_lines.get_last_payment()

    order_lines_to_return = order_with_lines.lines.all()
    original_quantity = {
        line.id: line.quantity_unfulfilled for line in order_with_lines
    }
    order_line_ids = order_lines_to_return.values_list("id", flat=True)
    original_allocations = list(
        Allocation.objects.filter(order_line_id__in=order_line_ids)
    )
    lines_count = order_with_lines.lines.count()

    response = create_fulfillments_for_returned_rooms(
        requester=staff_user,
        order=order_with_lines,
        payment=payment,
        order_lines=[
            OrderLineData(line=line, quantity=2, replace=False)
            for line in order_lines_to_return
        ],
        fulfillment_lines=[],
        plugin_manager=get_plugins_manager(),
        refund=True,
        refund_shipping_costs=True,
    )
    returned_fulfillment, replaced_fulfillment, replace_order = response

    returned_fulfillment_lines = returned_fulfillment.lines.all()
    assert returned_fulfillment.status == FulfillmentStatus.REFUNDED_AND_RETURNED
    assert len(returned_fulfillment_lines) == lines_count
    for fulfillment_line in returned_fulfillment_lines:
        assert fulfillment_line.quantity == 2
        assert fulfillment_line.order_line_id in order_line_ids
    for line in order_lines_to_return:
        assert line.quantity_unfulfilled == original_quantity.get(line.pk) - 2

    current_allocations = Allocation.objects.in_bulk(
        [allocation.pk for allocation in original_allocations]
    )
    for original_allocation in original_allocations:
        current_allocation = current_allocations.get(original_allocation.pk)
        assert (
            original_allocation.quantity_allocated - 2
            == current_allocation.quantity_allocated
        )

    amount = sum([line.unit_price_gross_amount * 2 for line in order_lines_to_return])
    amount += order_with_lines.shipping_price_gross_amount
    mocked_refund.assert_called_once_with(payment_dummy_fully_charged, amount)
    assert not replace_order


@patch("vanphong.order.actions.gateway.refund")
def test_create_return_fulfillment_only_order_lines_with_replace_request(
    mocked_refund, order_with_lines, payment_dummy_fully_charged, staff_user
):
    order_with_lines.payments.add(payment_dummy_fully_charged)
    payment = order_with_lines.get_last_payment()

    order_lines_to_return = order_with_lines.lines.all()
    original_quantity = {
        line.id: line.quantity_unfulfilled for line in order_with_lines
    }
    order_line_ids = order_lines_to_return.values_list("id", flat=True)
    original_allocations = list(
        Allocation.objects.filter(order_line_id__in=order_line_ids)
    )
    lines_count = order_with_lines.lines.count()
    quantity_to_replace = 2
    order_lines_data = [
        OrderLineData(line=line, quantity=2, replace=False)
        for line in order_lines_to_return
    ]

    # set replace request for the first line
    order_lines_data[0].replace = True
    order_lines_data[0].quantity = quantity_to_replace

    response = create_fulfillments_for_returned_rooms(
        requester=staff_user,
        order=order_with_lines,
        payment=payment,
        order_lines=order_lines_data,
        fulfillment_lines=[],
        plugin_manager=get_plugins_manager(),
    )
    returned_fulfillment, replaced_fulfillment, replace_order = response

    returned_fulfillment_lines = returned_fulfillment.lines.all()
    assert returned_fulfillment.status == FulfillmentStatus.RETURNED
    # we replaced one line
    assert len(returned_fulfillment_lines) == lines_count - 1

    for fulfillment_line in returned_fulfillment_lines:
        assert fulfillment_line.quantity == 2
        assert fulfillment_line.order_line_id in order_line_ids

    order_lines_to_return = order_with_lines.lines.all()
    for line in order_lines_to_return:
        assert line.quantity_unfulfilled == original_quantity.get(line.pk) - 2

    replaced_fulfillment_lines = replaced_fulfillment.lines.all()
    assert replaced_fulfillment_lines.count() == 1
    assert replaced_fulfillment_lines[0].quantity == quantity_to_replace
    assert replaced_fulfillment_lines[0].order_line_id == order_lines_data[0].line.id

    current_allocations = Allocation.objects.in_bulk(
        [allocation.pk for allocation in original_allocations]
    )
    for original_allocation in original_allocations:
        current_allocation = current_allocations.get(original_allocation.pk)
        assert (
            original_allocation.quantity_allocated - 2
            == current_allocation.quantity_allocated
        )

    order_with_lines.refresh_from_db()

    # refund should not be called
    assert not mocked_refund.called

    # new order should have own id
    assert replace_order.id != order_with_lines.id

    # make sure that we have new instances of addresses
    assert replace_order.shipping_address.id != order_with_lines.shipping_address.id
    assert replace_order.billing_address.id != order_with_lines.billing_address.id

    # the rest of address data should be the same
    replace_order.shipping_address.id = None
    order_with_lines.shipping_address.id = None
    assert replace_order.shipping_address == order_with_lines.shipping_address

    replace_order.billing_address.id = None
    order_with_lines.billing_address.id = None
    assert replace_order.billing_address == order_with_lines.billing_address

    expected_replaced_line = order_lines_to_return[0]

    assert replace_order.lines.count() == 1
    replaced_line = replace_order.lines.first()
    # make sure that all data from original line is in replaced line
    assert replaced_line.variant_id == expected_replaced_line.variant_id
    assert replaced_line.room_name == expected_replaced_line.room_name
    assert replaced_line.variant_name == expected_replaced_line.variant_name
    assert replaced_line.room_sku == expected_replaced_line.room_sku
    assert (
        replaced_line.is_shipping_required
        == expected_replaced_line.is_shipping_required
    )
    assert replaced_line.quantity == quantity_to_replace
    assert replaced_line.quantity_fulfilled == 0
    assert replaced_line.currency == expected_replaced_line.currency
    assert (
        replaced_line.unit_price_net_amount
        == expected_replaced_line.unit_price_net_amount
    )
    assert (
        replaced_line.unit_price_gross_amount
        == expected_replaced_line.unit_price_gross_amount
    )
    assert replaced_line.tax_rate == expected_replaced_line.tax_rate


@patch("vanphong.order.actions.gateway.refund")
def test_create_return_fulfillment_multiple_order_line_returns(
    mocked_refund, order_with_lines, payment_dummy_fully_charged, staff_user
):
    order_with_lines.payments.add(payment_dummy_fully_charged)
    payment = order_with_lines.get_last_payment()
    order_lines_to_return = order_with_lines.lines.all()
    original_quantity = {
        line.id: line.quantity_unfulfilled for line in order_with_lines
    }
    order_line_ids = order_lines_to_return.values_list("id", flat=True)
    lines_count = order_lines_to_return.count()

    for _ in range(2):
        # call refund two times
        create_fulfillments_for_returned_rooms(
            requester=staff_user,
            order=order_with_lines,
            payment=payment,
            order_lines=[
                OrderLineData(line=line, quantity=1) for line in order_lines_to_return
            ],
            fulfillment_lines=[],
            plugin_manager=get_plugins_manager(),
            refund=True,
        )

    returned_fulfillemnt = Fulfillment.objects.get(
        order=order_with_lines, status=FulfillmentStatus.REFUNDED_AND_RETURNED
    )
    returned_fulfillment_lines = returned_fulfillemnt.lines.all()
    assert len(returned_fulfillment_lines) == lines_count
    for fulfillment_line in returned_fulfillment_lines:
        assert fulfillment_line.quantity == 2
        assert fulfillment_line.order_line_id in order_line_ids
    for line in order_lines_to_return:
        assert line.quantity_unfulfilled == original_quantity.get(line.pk) - 2

    assert mocked_refund.call_count == 2


@patch("vanphong.order.actions.gateway.refund")
def test_create_return_fulfillment_only_fulfillment_lines(
    mocked_refund, fulfilled_order, payment_dummy_fully_charged, staff_user
):
    fulfilled_order.payments.add(payment_dummy_fully_charged)
    payment = fulfilled_order.get_last_payment()
    order_line_ids = fulfilled_order.lines.all().values_list("id", flat=True)
    fulfillment_lines = FulfillmentLine.objects.filter(order_line_id__in=order_line_ids)
    original_quantity = {line.id: line.quantity for line in fulfillment_lines}

    response = create_fulfillments_for_returned_rooms(
        requester=staff_user,
        order=fulfilled_order,
        payment=payment,
        order_lines=[],
        fulfillment_lines=[
            FulfillmentLineData(line=line, quantity=2, replace=False)
            for line in fulfillment_lines
        ],
        plugin_manager=get_plugins_manager(),
    )

    returned_fulfillment, replaced_fulfillment, replace_order = response

    returned_fulfillment_lines = returned_fulfillment.lines.all()
    assert returned_fulfillment.status == FulfillmentStatus.RETURNED
    assert returned_fulfillment_lines.count() == len(order_line_ids)

    for fulfillment_line in returned_fulfillment_lines:
        assert fulfillment_line.quantity == 2
        assert fulfillment_line.order_line_id in order_line_ids

    for line in fulfillment_lines:
        assert line.quantity == original_quantity.get(line.pk) - 2

    assert not mocked_refund.called
    assert not replace_order


@patch("vanphong.order.actions.gateway.refund")
def test_create_return_fulfillment_only_fulfillment_lines_replace_order(
    mocked_refund, fulfilled_order, payment_dummy_fully_charged, staff_user
):
    fulfilled_order.payments.add(payment_dummy_fully_charged)
    payment = fulfilled_order.get_last_payment()
    order_line_ids = fulfilled_order.lines.all().values_list("id", flat=True)
    fulfillment_lines = FulfillmentLine.objects.filter(order_line_id__in=order_line_ids)
    original_quantity = {line.id: line.quantity for line in fulfillment_lines}

    # Prepare the structure for return method
    fulfillment_lines_to_return = [
        FulfillmentLineData(line=line, quantity=2, replace=False)
        for line in fulfillment_lines
    ]
    # The line which should be replaced
    replace_quantity = 2
    fulfillment_lines_to_return[0].replace = True
    fulfillment_lines_to_return[0].quantity = replace_quantity

    response = create_fulfillments_for_returned_rooms(
        requester=staff_user,
        order=fulfilled_order,
        payment=payment,
        order_lines=[],
        fulfillment_lines=fulfillment_lines_to_return,
        plugin_manager=get_plugins_manager(),
    )

    returned_fulfillment, replaced_fulfillment, replace_order = response

    returned_fulfillment_lines = returned_fulfillment.lines.all()
    assert returned_fulfillment.status == FulfillmentStatus.RETURNED
    # make sure that all order lines from refund are in expected fulfillment
    # minus one as we replaced the one item
    assert returned_fulfillment_lines.count() == len(order_line_ids) - 1

    for fulfillment_line in returned_fulfillment_lines:
        assert fulfillment_line.quantity == 2
        assert fulfillment_line.order_line_id in order_line_ids

    for line in fulfillment_lines:
        assert line.quantity == original_quantity.get(line.pk) - 2

    replaced_fulfillment_lines = replaced_fulfillment.lines.all()
    assert replaced_fulfillment_lines.count() == 1
    assert replaced_fulfillment_lines[0].quantity == replace_quantity
    assert (
        replaced_fulfillment_lines[0].order_line_id
        == fulfillment_lines_to_return[0].line.order_line_id
    )

    assert not mocked_refund.called

    # new order should have own id
    assert replace_order.id != fulfilled_order.id

    # make sure that we have new instances of addresses
    assert replace_order.shipping_address.id != fulfilled_order.shipping_address.id
    assert replace_order.billing_address.id != fulfilled_order.billing_address.id

    # the rest of address data should be the same
    replace_order.shipping_address.id = None
    fulfilled_order.shipping_address.id = None
    assert replace_order.shipping_address == fulfilled_order.shipping_address

    replace_order.billing_address.id = None
    fulfilled_order.billing_address.id = None
    assert replace_order.billing_address == fulfilled_order.billing_address

    expected_replaced_line = fulfillment_lines[0].order_line

    assert replace_order.lines.count() == 1
    replaced_line = replace_order.lines.first()
    # make sure that all data from original line is in replaced line
    assert replaced_line.variant_id == expected_replaced_line.variant_id
    assert replaced_line.room_name == expected_replaced_line.room_name
    assert replaced_line.variant_name == expected_replaced_line.variant_name
    assert replaced_line.room_sku == expected_replaced_line.room_sku
    assert (
        replaced_line.is_shipping_required
        == expected_replaced_line.is_shipping_required
    )
    assert replaced_line.quantity == replace_quantity
    assert replaced_line.quantity_fulfilled == 0
    assert replaced_line.currency == expected_replaced_line.currency
    assert (
        replaced_line.unit_price_net_amount
        == expected_replaced_line.unit_price_net_amount
    )
    assert (
        replaced_line.unit_price_gross_amount
        == expected_replaced_line.unit_price_gross_amount
    )
    assert replaced_line.tax_rate == expected_replaced_line.tax_rate


@patch("vanphong.order.actions.gateway.refund")
def test_create_return_fulfillment_multiple_fulfillment_lines_returns(
    mocked_refund, fulfilled_order, payment_dummy_fully_charged, staff_user
):
    fulfilled_order.payments.add(payment_dummy_fully_charged)
    payment = fulfilled_order.get_last_payment()
    order_line_ids = fulfilled_order.lines.all().values_list("id", flat=True)
    fulfillment_lines = FulfillmentLine.objects.filter(order_line_id__in=order_line_ids)
    original_quantity = {line.id: line.quantity for line in fulfillment_lines}
    fulfillment_lines_to_return = fulfillment_lines

    for _ in range(2):
        create_fulfillments_for_returned_rooms(
            requester=staff_user,
            order=fulfilled_order,
            payment=payment,
            order_lines=[],
            fulfillment_lines=[
                FulfillmentLineData(line=line, quantity=1)
                for line in fulfillment_lines_to_return
            ],
            plugin_manager=get_plugins_manager(),
            refund=True,
        )

    returned_fulfillment = Fulfillment.objects.get(
        order=fulfilled_order, status=FulfillmentStatus.REFUNDED_AND_RETURNED
    )
    returned_fulfillment_lines = returned_fulfillment.lines.all()

    assert returned_fulfillment_lines.count() == len(order_line_ids)
    for fulfillment_line in returned_fulfillment_lines:
        assert fulfillment_line.quantity == 2
        assert fulfillment_line.order_line_id in order_line_ids

    for line in fulfillment_lines:
        assert line.quantity == original_quantity.get(line.pk) - 2

    assert mocked_refund.call_count == 2


@patch("vanphong.order.actions.gateway.refund")
def test_create_return_fulfillment_multiple_lines_returns(
    mocked_refund,
    fulfilled_order,
    payment_dummy_fully_charged,
    staff_user,
    channel_USD,
    variant,
    hotel,
):
    fulfilled_order.payments.add(payment_dummy_fully_charged)
    payment = fulfilled_order.get_last_payment()
    order_line_ids = fulfilled_order.lines.all().values_list("id", flat=True)
    fulfillment_lines = FulfillmentLine.objects.filter(order_line_id__in=order_line_ids)
    original_quantity = {line.id: line.quantity for line in fulfillment_lines}
    fulfillment_lines_to_return = fulfillment_lines

    stock = Stock.objects.create(
        hotel=hotel, room_variant=variant, quantity=5
    )

    channel_listing = variant.channel_listings.get()
    net = variant.get_price(variant.room, [], channel_USD, channel_listing)

    gross = Money(amount=net.amount * Decimal(1.23), currency=net.currency)
    unit_price = TaxedMoney(net=net, gross=gross)
    quantity = 5
    order_line = fulfilled_order.lines.create(
        room_name=str(variant.room),
        variant_name=str(variant),
        room_sku=variant.sku,
        is_shipping_required=variant.is_shipping_required(),
        quantity=quantity,
        quantity_fulfilled=2,
        variant=variant,
        unit_price=TaxedMoney(net=net, gross=gross),
        tax_rate=Decimal("0.23"),
        total_price=unit_price * quantity,
    )
    Allocation.objects.create(
        order_line=order_line, stock=stock, quantity_allocated=order_line.quantity
    )

    for _ in range(2):
        create_fulfillments_for_returned_rooms(
            requester=staff_user,
            order=fulfilled_order,
            payment=payment,
            order_lines=[OrderLineData(line=order_line, quantity=1)],
            fulfillment_lines=[
                FulfillmentLineData(line=line, quantity=1)
                for line in fulfillment_lines_to_return
            ],
            plugin_manager=get_plugins_manager(),
            refund=True,
        )

    returned_fulfillment = Fulfillment.objects.get(
        order=fulfilled_order, status=FulfillmentStatus.REFUNDED_AND_RETURNED
    )
    returned_fulfillment_lines = returned_fulfillment.lines.all()

    assert returned_fulfillment_lines.count() == len(order_line_ids)
    for fulfillment_line in returned_fulfillment_lines:
        assert fulfillment_line.quantity == 2
        assert fulfillment_line.order_line_id in order_line_ids

    for line in fulfillment_lines:
        assert line.quantity == original_quantity.get(line.pk) - 2

    assert mocked_refund.call_count == 2


@patch("vanphong.order.actions.gateway.refund")
def test_create_return_fulfillment_multiple_lines_without_refund(
    mocked_refund,
    fulfilled_order,
    payment_dummy_fully_charged,
    staff_user,
    channel_USD,
    variant,
    hotel,
):
    fulfilled_order.payments.add(payment_dummy_fully_charged)
    payment = fulfilled_order.get_last_payment()
    order_line_ids = fulfilled_order.lines.all().values_list("id", flat=True)
    fulfillment_lines = FulfillmentLine.objects.filter(order_line_id__in=order_line_ids)
    original_quantity = {line.id: line.quantity for line in fulfillment_lines}
    fulfillment_lines_to_return = fulfillment_lines

    stock = Stock.objects.create(
        hotel=hotel, room_variant=variant, quantity=5
    )

    channel_listing = variant.channel_listings.get()
    net = variant.get_price(variant.room, [], channel_USD, channel_listing)
    gross = Money(amount=net.amount * Decimal(1.23), currency=net.currency)
    unit_price = TaxedMoney(net=net, gross=gross)
    quantity = 5
    order_line = fulfilled_order.lines.create(
        room_name=str(variant.room),
        variant_name=str(variant),
        room_sku=variant.sku,
        is_shipping_required=variant.is_shipping_required(),
        quantity=quantity,
        quantity_fulfilled=2,
        variant=variant,
        unit_price=TaxedMoney(net=net, gross=gross),
        tax_rate=Decimal("0.23"),
        total_price=unit_price * quantity,
    )
    Allocation.objects.create(
        order_line=order_line, stock=stock, quantity_allocated=order_line.quantity
    )
    refunded_fulfillment = Fulfillment.objects.create(
        order=fulfilled_order, status=FulfillmentStatus.REFUNDED
    )
    refunded_fulfillment_line = refunded_fulfillment.lines.create(
        order_line=order_line, quantity=2
    )

    fulfillment_lines_to_process = [
        FulfillmentLineData(line=line, quantity=1)
        for line in fulfillment_lines_to_return
    ]
    fulfillment_lines_to_process.append(
        FulfillmentLineData(line=refunded_fulfillment_line, quantity=1)
    )
    for _ in range(2):
        create_fulfillments_for_returned_rooms(
            requester=staff_user,
            order=fulfilled_order,
            payment=payment,
            order_lines=[OrderLineData(line=order_line, quantity=1)],
            fulfillment_lines=fulfillment_lines_to_process,
            plugin_manager=get_plugins_manager(),
            refund=False,
        )

    returned_fulfillment = Fulfillment.objects.get(
        order=fulfilled_order, status=FulfillmentStatus.RETURNED
    )
    returned_fulfillment_lines = returned_fulfillment.lines.all()

    returned_and_refunded_fulfillment = Fulfillment.objects.get(
        order=fulfilled_order, status=FulfillmentStatus.REFUNDED_AND_RETURNED
    )
    returned_and_refunded_lines = returned_and_refunded_fulfillment.lines.all()

    assert returned_fulfillment_lines.count() == len(order_line_ids)
    for fulfillment_line in returned_fulfillment_lines:
        assert fulfillment_line.quantity == 2
        assert fulfillment_line.order_line_id in order_line_ids

    for line in fulfillment_lines:
        assert line.quantity == original_quantity.get(line.pk) - 2

    assert returned_and_refunded_lines.count() == 1
    assert returned_and_refunded_lines[0].order_line_id == order_line.id

    assert not mocked_refund.called


@patch("vanphong.order.actions.gateway.refund")
def test_create_return_fulfillment_with_lines_already_refunded(
    mocked_refund,
    fulfilled_order,
    payment_dummy_fully_charged,
    staff_user,
    channel_USD,
    variant,
    hotel,
):
    fulfilled_order.payments.add(payment_dummy_fully_charged)
    payment = fulfilled_order.get_last_payment()
    order_line_ids = fulfilled_order.lines.all().values_list("id", flat=True)
    fulfillment_lines = FulfillmentLine.objects.filter(order_line_id__in=order_line_ids)
    original_quantity = {line.id: line.quantity for line in fulfillment_lines}
    fulfillment_lines_to_return = fulfillment_lines

    stock = Stock.objects.create(
        hotel=hotel, room_variant=variant, quantity=5
    )

    channel_listing = variant.channel_listings.get()
    net = variant.get_price(variant.room, [], channel_USD, channel_listing)
    gross = Money(amount=net.amount * Decimal(1.23), currency=net.currency)
    unit_price = TaxedMoney(net=net, gross=gross)
    quantity = 5
    order_line = fulfilled_order.lines.create(
        room_name=str(variant.room),
        variant_name=str(variant),
        room_sku=variant.sku,
        is_shipping_required=variant.is_shipping_required(),
        quantity=quantity,
        quantity_fulfilled=2,
        variant=variant,
        unit_price=unit_price,
        tax_rate=Decimal("0.23"),
        total_price=unit_price * quantity,
    )
    Allocation.objects.create(
        order_line=order_line, stock=stock, quantity_allocated=order_line.quantity
    )
    refunded_fulfillment = Fulfillment.objects.create(
        order=fulfilled_order, status=FulfillmentStatus.REFUNDED
    )
    refunded_fulfillment_line = refunded_fulfillment.lines.create(
        order_line=order_line, quantity=2
    )

    fulfillment_lines_to_process = [
        FulfillmentLineData(line=line, quantity=2)
        for line in fulfillment_lines_to_return
    ]
    fulfillment_lines_to_process.append(
        FulfillmentLineData(line=refunded_fulfillment_line, quantity=2)
    )
    create_fulfillments_for_returned_rooms(
        requester=staff_user,
        order=fulfilled_order,
        payment=payment,
        order_lines=[],
        fulfillment_lines=fulfillment_lines_to_process,
        plugin_manager=get_plugins_manager(),
        refund=True,
    )

    returned_and_refunded_fulfillment = Fulfillment.objects.get(
        order=fulfilled_order, status=FulfillmentStatus.REFUNDED_AND_RETURNED
    )
    returned_and_refunded_lines = returned_and_refunded_fulfillment.lines.all()

    assert returned_and_refunded_lines.count() == len(order_line_ids)
    for fulfillment_line in returned_and_refunded_lines:
        assert fulfillment_line.quantity == 2
        assert fulfillment_line.order_line_id in order_line_ids

    for line in fulfillment_lines:
        assert line.quantity == original_quantity.get(line.pk) - 2

    # the already refunded line is not included in amount
    amount = sum(
        [
            line.order_line.unit_price_gross_amount * 2
            for line in fulfillment_lines_to_return
        ]
    )
    mocked_refund.assert_called_once_with(payment_dummy_fully_charged, amount)