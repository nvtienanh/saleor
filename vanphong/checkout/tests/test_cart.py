import pytest
from measurement.measures import Weight
from prices import Money, TaxedMoney

from ...checkout.utils import fetch_checkout_lines
from ...plugins.manager import get_plugins_manager
from ...room.models import Category
from .. import calculations, utils
from ..models import Checkout
from ..utils import add_variant_to_checkout


@pytest.fixture()
def anonymous_checkout(db, channel_USD):
    return Checkout.objects.get_or_create(user=None, channel=channel_USD)[0]


def test_get_user_checkout(
    anonymous_checkout, user_checkout, admin_user, customer_user
):
    checkout = utils.get_user_checkout(customer_user)
    assert Checkout.objects.all().count() == 2
    assert checkout == user_checkout


def test_adding_zero_quantity(checkout, room):
    variant = room.variants.get()
    add_variant_to_checkout(checkout, variant, 0)
    assert checkout.lines.count() == 0


def test_adding_same_variant(checkout, room):
    variant = room.variants.get()
    add_variant_to_checkout(checkout, variant, 1)
    add_variant_to_checkout(checkout, variant, 2)
    assert checkout.lines.count() == 1
    assert checkout.quantity == 3
    subtotal = TaxedMoney(Money("30.00", "USD"), Money("30.00", "USD"))
    lines = fetch_checkout_lines(checkout)
    manager = get_plugins_manager()
    assert (
        calculations.checkout_subtotal(
            manager=manager,
            checkout=checkout,
            lines=lines,
            address=checkout.shipping_address,
        )
        == subtotal
    )


def test_replacing_same_variant(checkout, room):
    variant = room.variants.get()
    add_variant_to_checkout(checkout, variant, 1, replace=True)
    add_variant_to_checkout(checkout, variant, 2, replace=True)
    assert checkout.lines.count() == 1
    assert checkout.quantity == 2


def test_adding_invalid_quantity(checkout, room):
    variant = room.variants.get()
    with pytest.raises(ValueError):
        add_variant_to_checkout(checkout, variant, -1)


def test_getting_line(checkout, room):
    variant = room.variants.get()
    assert checkout.get_line(variant) is None
    add_variant_to_checkout(checkout, variant)
    assert checkout.lines.get() == checkout.get_line(variant)


def test_shipping_detection(checkout, room):
    assert not checkout.is_shipping_required()
    variant = room.variants.get()
    add_variant_to_checkout(checkout, variant, replace=True)
    assert checkout.is_shipping_required()


def test_get_prices_of_discounted_specific_room(
    checkout_with_item, collection, voucher_specific_room_type
):
    checkout = checkout_with_item
    voucher = voucher_specific_room_type
    line = checkout.lines.first()
    room = line.variant.room
    category = room.category
    channel = checkout.channel
    variant_channel_listing = line.variant.channel_listings.get(channel=channel)

    room.collections.add(collection)
    voucher.rooms.add(room)
    voucher.collections.add(collection)
    voucher.categories.add(category)

    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout)
    prices = utils.get_prices_of_discounted_specific_room(
        manager, checkout, lines, voucher, channel
    )

    excepted_value = [
        line.variant.get_price(
            room, [collection], channel, variant_channel_listing, []
        )
        for item in range(line.quantity)
    ]

    assert prices == excepted_value


def test_get_prices_of_discounted_specific_room_only_room(
    checkout_with_item, voucher_specific_room_type, room_with_default_variant
):
    checkout = checkout_with_item
    voucher = voucher_specific_room_type
    line = checkout.lines.first()
    room = line.variant.room
    room2 = room_with_default_variant
    channel = checkout.channel
    variant_channel_listing = line.variant.channel_listings.get(channel=channel)

    add_variant_to_checkout(checkout, room2.variants.get(), 1)
    voucher.rooms.add(room)

    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout)
    prices = utils.get_prices_of_discounted_specific_room(
        manager, checkout, lines, voucher, channel
    )

    excepted_value = [
        line.variant.get_price(room, [], channel, variant_channel_listing, [])
        for item in range(line.quantity)
    ]

    assert checkout.lines.count() > 1
    assert prices == excepted_value


def test_get_prices_of_discounted_specific_room_only_collection(
    checkout_with_item,
    collection,
    voucher_specific_room_type,
    room_with_default_variant,
):
    checkout = checkout_with_item
    voucher = voucher_specific_room_type
    line = checkout.lines.first()
    room = line.variant.room
    room2 = room_with_default_variant
    channel = checkout.channel
    variant_channel_listing = line.variant.channel_listings.get(channel=channel)

    add_variant_to_checkout(checkout, room2.variants.get(), 1)
    room.collections.add(collection)
    voucher.collections.add(collection)

    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout)
    prices = utils.get_prices_of_discounted_specific_room(
        manager, checkout, lines, voucher, checkout.channel
    )

    excepted_value = [
        line.variant.get_price(
            room, [collection], channel, variant_channel_listing, []
        )
        for item in range(line.quantity)
    ]

    assert checkout.lines.count() > 1
    assert prices == excepted_value


def test_get_prices_of_discounted_specific_room_only_category(
    checkout_with_item, voucher_specific_room_type, room_with_default_variant
):
    checkout = checkout_with_item
    voucher = voucher_specific_room_type
    line = checkout.lines.first()
    room = line.variant.room
    room2 = room_with_default_variant
    category = room.category
    category2 = Category.objects.create(name="Cat", slug="cat")
    channel = checkout.channel
    variant_channel_listing = line.variant.channel_listings.get(channel=channel)

    room2.category = category2
    room2.save()
    add_variant_to_checkout(checkout, room2.variants.get(), 1)
    voucher.categories.add(category)

    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout)
    prices = utils.get_prices_of_discounted_specific_room(
        manager, checkout, lines, voucher, channel
    )

    excepted_value = [
        line.variant.get_price(room, [], channel, variant_channel_listing, [])
        for item in range(line.quantity)
    ]

    assert checkout.lines.count() > 1
    assert prices == excepted_value


def test_get_prices_of_discounted_specific_room_all_rooms(
    checkout_with_item, voucher_specific_room_type
):
    checkout = checkout_with_item
    voucher = voucher_specific_room_type
    line = checkout.lines.first()
    room = line.variant.room
    channel = checkout.channel
    variant_channel_listing = line.variant.channel_listings.get(channel=channel)

    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout)
    prices = utils.get_prices_of_discounted_specific_room(
        manager, checkout, lines, voucher, channel
    )

    excepted_value = [
        line.variant.get_price(room, [], channel, variant_channel_listing, [])
        for item in range(line.quantity)
    ]

    assert prices == excepted_value


def test_checkout_repr():
    checkout = Checkout()
    assert repr(checkout) == "Checkout(quantity=0)"

    checkout.quantity = 1
    assert repr(checkout) == "Checkout(quantity=1)"


def test_checkout_line_repr(room, checkout_with_single_item):
    variant = room.variants.get()
    line = checkout_with_single_item.lines.first()
    assert repr(line) == "CheckoutLine(variant=%r, quantity=%r)" % (
        variant,
        line.quantity,
    )


def test_checkout_line_state(room, checkout_with_single_item):
    variant = room.variants.get()
    line = checkout_with_single_item.lines.first()

    assert line.__getstate__() == (variant, line.quantity)

    line.__setstate__((variant, 2))

    assert line.quantity == 2


def test_get_total_weight(checkout_with_item):
    line = checkout_with_item.lines.first()
    variant = line.variant
    variant.weight = Weight(kg=10)
    variant.save()
    line.quantity = 6
    line.save()
    assert checkout_with_item.get_total_weight() == Weight(kg=60)