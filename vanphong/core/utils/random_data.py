import itertools
import json
import os
import random
import unicodedata
import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Type, Union
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.sites.models import Site
from django.core.files import File
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from faker import Factory
from faker.providers import BaseProvider
from measurement.measures import Weight
from prices import Money, TaxedMoney

from ...account.models import Address, User
from ...account.utils import store_user_address
from ...attribute.models import (
    AssignedPageAttribute,
    AssignedRoomAttribute,
    AssignedVariantAttribute,
    Attribute,
    AttributePage,
    AttributeRoom,
    AttributeValue,
    AttributeVariant,
)
from ...channel.models import Channel
from ...checkout import AddressType
from ...core.permissions import (
    AccountPermissions,
    CheckoutPermissions,
    GiftcardPermissions,
    OrderPermissions,
    get_permissions,
)
from ...core.utils import build_absolute_uri
from ...core.weight import zero_weight
from ...discount import DiscountValueType, VoucherType
from ...discount.models import Sale, SaleChannelListing, Voucher, VoucherChannelListing
from ...discount.utils import fetch_discounts
from ...giftcard.models import GiftCard
from ...menu.models import Menu
from ...order import OrderStatus
from ...order.models import Fulfillment, Order, OrderLine
from ...order.utils import update_order_status
from ...page.models import Page, PageType
from ...payment import gateway
from ...payment.utils import create_payment
from ...plugins.manager import get_plugins_manager
from ...room.models import (
    Category,
    Collection,
    CollectionChannelListing,
    CollectionRoom,
    Room,
    RoomChannelListing,
    RoomImage,
    RoomType,
    RoomVariant,
    RoomVariantChannelListing,
    VariantImage,
)
from ...room.tasks import update_rooms_discounted_prices_of_discount_task
from ...room.thumbnails import (
    create_category_background_image_thumbnails,
    create_collection_background_image_thumbnails,
    create_room_thumbnails,
)
from ...shipping.models import (
    ShippingMethod,
    ShippingMethodChannelListing,
    ShippingMethodType,
    ShippingZone,
)
from ...hotel.management import increase_stock
from ...hotel.models import Stock, Hotel
from ...place.models import Place

fake = Factory.create()
ROOMS_LIST_DIR = "rooms-list/"

DUMMY_STAFF_PASSWORD = "password"

IMAGES_MAPPING = {
    61: ["vanphongdemoroom_paints_01.png"],
    62: ["vanphongdemoroom_paints_02.png"],
    63: ["vanphongdemoroom_paints_03.png"],
    64: ["vanphongdemoroom_paints_04.png"],
    65: ["vanphongdemoroom_paints_05.png"],
    71: ["vanphongdemoroom_fd_juice_06.png"],
    72: ["vanphongdemoroom_fd_juice_06.png"],  # FIXME inproper image
    73: ["vanphongdemoroom_fd_juice_05.png"],
    74: ["vanphongdemoroom_fd_juice_01.png"],
    75: ["vanphongdemoroom_fd_juice_03.png"],  # FIXME inproper image
    76: ["vanphongdemoroom_fd_juice_02.png"],  # FIXME inproper image
    77: ["vanphongdemoroom_fd_juice_03.png"],
    78: ["vanphongdemoroom_fd_juice_04.png"],
    79: ["vanphongdemoroom_fd_juice_02.png"],
    81: ["vanphongdemoroom_wine-red.png"],
    82: ["vanphongdemoroom_wine-white.png"],
    83: ["vanphongdemoroom_beer-02_1.png", "vanphongdemoroom_beer-02_2.png"],
    84: ["vanphongdemoroom_beer-01_1.png", "vanphongdemoroom_beer-01_2.png"],
    85: ["vanphongdemoroom_cuschion01.png"],
    86: ["vanphongdemoroom_cuschion02.png"],
    87: [
        "vanphongdemoroom_sneakers_01_1.png",
        "vanphongdemoroom_sneakers_01_2.png",
        "vanphongdemoroom_sneakers_01_3.png",
        "vanphongdemoroom_sneakers_01_4.png",
    ],
    88: [
        "vanphongdemoroom_sneakers_02_1.png",
        "vanphongdemoroom_sneakers_02_2.png",
        "vanphongdemoroom_sneakers_02_3.png",
        "vanphongdemoroom_sneakers_02_4.png",
    ],
    89: ["vanphongdemoroom_cl_boot07_1.png", "vanphongdemoroom_cl_boot07_2.png"],
    107: ["vanphongdemoroom_cl_polo01.png"],
    108: ["vanphongdemoroom_cl_polo02.png"],
    109: ["vanphongdemoroom_cl_polo03-woman.png"],
    110: ["vanphongdemoroom_cl_polo04-woman.png"],
    111: [
        "vanphongdemoroom_cl_boot01_1.png",
        "vanphongdemoroom_cl_boot01_2.png",
        "vanphongdemoroom_cl_boot01_3.png",
    ],
    112: ["vanphongdemoroom_cl_boot03_1.png", "vanphongdemoroom_cl_boot03_2.png"],
    113: ["vanphongdemoroom_cl_boot06_1.png", "vanphongdemoroom_cl_boot06_2.png"],
    114: [
        "vanphongdemoroom_cl_boot06_1.png",
        "vanphongdemoroom_cl_boot06_2.png",
    ],  # FIXME incorrect image
    115: ["vanphongdemoroom_cl_bogo01_1.png"],
    116: ["vanphongdemoroom_cl_bogo02_1.png"],
    117: ["vanphongdemoroom_cl_bogo03_1.png"],
    118: ["vanphongdemoroom_cl_bogo04_1.png", "vanphongdemoroom_cl_bogo04_2.png"],
    119: ["vanphong-digital-03_1.png"],
    120: ["vanphong-digital-03_2.png"],
    121: ["vanphong-digital-03_3.png"],
    122: ["vanphong-digital-03_4.png"],
    123: ["vanphong-digital-03_5.png"],
    124: ["vanphong-digital-03_6.png"],
}


CATEGORY_IMAGES = {7: "accessories.jpg", 8: "groceries.jpg", 9: "apparel.jpg"}

COLLECTION_IMAGES = {1: "summer.jpg", 2: "clothing.jpg", 3: "clothing.jpg"}


def get_weight(weight):
    if not weight:
        return zero_weight()
    value, unit = weight.split(":")
    return Weight(**{unit: value})


def create_room_types(room_type_data):
    for room_type in room_type_data:
        pk = room_type["pk"]
        defaults = room_type["fields"]
        # defaults["weight"] = get_weight(defaults["weight"])
        RoomType.objects.update_or_create(pk=pk, defaults=defaults)


def create_categories(categories_data, placeholder_dir):
    placeholder_dir = get_room_list_images_dir(placeholder_dir)
    for category in categories_data:
        pk = category["pk"]
        defaults = category["fields"]
        parent = defaults["parent"]
        image_name = (
            CATEGORY_IMAGES[pk] if pk in CATEGORY_IMAGES else CATEGORY_IMAGES[parent]
        )
        background_image = get_image(placeholder_dir, image_name)
        defaults["background_image"] = background_image
        if parent:
            defaults["parent"] = Category.objects.get(pk=parent)
        Category.objects.update_or_create(pk=pk, defaults=defaults)
        create_category_background_image_thumbnails.delay(pk)


def create_collection_channel_listings(collection_channel_listings_data):
    channel_USD = Channel.objects.get(currency_code="USD")
    channel_PLN = Channel.objects.get(currency_code="PLN")
    for collection_channel_listing in collection_channel_listings_data:
        pk = collection_channel_listing["pk"]
        defaults = collection_channel_listing["fields"]
        defaults["collection_id"] = defaults.pop("collection")
        channel = defaults.pop("channel")
        defaults["channel_id"] = channel_USD.pk if channel == 1 else channel_PLN.pk
        CollectionChannelListing.objects.update_or_create(pk=pk, defaults=defaults)


def create_collections(data, placeholder_dir):
    placeholder_dir = get_room_list_images_dir(placeholder_dir)
    for collection in data:
        pk = collection["pk"]
        defaults = collection["fields"]
        image_name = COLLECTION_IMAGES[pk]
        background_image = get_image(placeholder_dir, image_name)
        defaults["background_image"] = background_image
        Collection.objects.update_or_create(pk=pk, defaults=defaults)
        create_collection_background_image_thumbnails.delay(pk)


def assign_rooms_to_collections(associations: list):
    for value in associations:
        pk = value["pk"]
        defaults = value["fields"]
        defaults["collection_id"] = defaults.pop("collection")
        defaults["room_id"] = defaults.pop("room")
        CollectionRoom.objects.update_or_create(pk=pk, defaults=defaults)


def create_attributes(attributes_data):
    for attribute in attributes_data:
        pk = attribute["pk"]
        defaults = attribute["fields"]
        attr, _ = Attribute.objects.update_or_create(pk=pk, defaults=defaults)


def create_attributes_values(values_data):
    for value in values_data:
        pk = value["pk"]
        defaults = value["fields"]
        defaults["attribute_id"] = defaults.pop("attribute")
        AttributeValue.objects.update_or_create(pk=pk, defaults=defaults)


def create_rooms(rooms_data, placeholder_dir, create_images):
    for room in rooms_data:
        pk = room["pk"]
        # We are skipping rooms without images
        if pk not in IMAGES_MAPPING:
            continue

        defaults = room["fields"]
        # defaults["weight"] = get_weight(defaults["weight"])
        defaults["category_id"] = defaults.pop("category")
        defaults["room_type_id"] = defaults.pop("room_type")

        room, _ = Room.objects.update_or_create(pk=pk, defaults=defaults)

        if create_images:
            images = IMAGES_MAPPING.get(pk, [])
            for image_name in images:
                create_room_image(room, placeholder_dir, image_name)


def create_room_channel_listings(room_channel_listings_data):
    channel_USD = Channel.objects.get(currency_code="USD")
    channel_PLN = Channel.objects.get(currency_code="PLN")
    for room_channel_listing in room_channel_listings_data:
        pk = room_channel_listing["pk"]
        defaults = room_channel_listing["fields"]
        defaults["room_id"] = defaults.pop("room")
        channel = defaults.pop("channel")
        defaults["channel_id"] = channel_USD.pk if channel == 1 else channel_PLN.pk
        RoomChannelListing.objects.update_or_create(pk=pk, defaults=defaults)


def create_stocks(variant, hotel_qs=None, **defaults):
    if hotel_qs is None:
        hotel_qs = Hotel.objects.all()

    for hotel in hotel_qs:
        Stock.objects.update_or_create(
            hotel=hotel, room_variant=variant, defaults=defaults
        )


def create_room_variants(variants_data, create_images):
    for variant in variants_data:
        pk = variant["pk"]
        defaults = variant["fields"]
        # defaults["weight"] = get_weight(defaults["weight"])
        room_id = defaults.pop("room")
        # We have not created rooms without images
        if room_id not in IMAGES_MAPPING:
            continue
        defaults["room_id"] = room_id
        set_field_as_money(defaults, "price_override")
        set_field_as_money(defaults, "cost_price")
        is_default_variant = defaults.pop("default", False)
        variant, _ = RoomVariant.objects.update_or_create(pk=pk, defaults=defaults)
        if is_default_variant:
            room = variant.room
            room.default_variant = variant
            room.save(update_fields=["default_variant", "updated_at"])
        if create_images:
            image = variant.room.images.filter().first()
            VariantImage.objects.get_or_create(variant=variant, image=image)
        quantity = random.randint(100, 500)
        create_stocks(variant, quantity=quantity)


def create_room_variant_channel_listings(room_variant_channel_listings_data):
    channel_USD = Channel.objects.get(currency_code="USD")
    channel_PLN = Channel.objects.get(currency_code="PLN")
    for variant_channel_listing in room_variant_channel_listings_data:
        pk = variant_channel_listing["pk"]
        defaults = variant_channel_listing["fields"]

        defaults["variant_id"] = defaults.pop("variant")
        channel = defaults.pop("channel")
        defaults["channel_id"] = channel_USD.pk if channel == 1 else channel_PLN.pk
        RoomVariantChannelListing.objects.update_or_create(pk=pk, defaults=defaults)


def assign_attributes_to_room_types(
    association_model: Union[Type[AttributeRoom], Type[AttributeVariant]],
    attributes: list,
):
    for value in attributes:
        pk = value["pk"]
        defaults = value["fields"]
        defaults["attribute_id"] = defaults.pop("attribute")
        defaults["room_type_id"] = defaults.pop("room_type")
        association_model.objects.update_or_create(pk=pk, defaults=defaults)


def assign_attributes_to_page_types(
    association_model: AttributePage,
    attributes: list,
):
    for value in attributes:
        pk = value["pk"]
        defaults = value["fields"]
        defaults["attribute_id"] = defaults.pop("attribute")
        defaults["page_type_id"] = defaults.pop("page_type")
        association_model.objects.update_or_create(pk=pk, defaults=defaults)


def assign_attributes_to_rooms(room_attributes):
    for value in room_attributes:
        pk = value["pk"]
        defaults = value["fields"]
        defaults["room_id"] = defaults.pop("room")
        defaults["assignment_id"] = defaults.pop("assignment")
        assigned_values = defaults.pop("values")
        assoc, created = AssignedRoomAttribute.objects.update_or_create(
            pk=pk, defaults=defaults
        )
        if created:
            assoc.values.set(AttributeValue.objects.filter(pk__in=assigned_values))


def assign_attributes_to_variants(variant_attributes):
    for value in variant_attributes:
        pk = value["pk"]
        defaults = value["fields"]
        defaults["variant_id"] = defaults.pop("variant")
        defaults["assignment_id"] = defaults.pop("assignment")
        assigned_values = defaults.pop("values")
        assoc, created = AssignedVariantAttribute.objects.update_or_create(
            pk=pk, defaults=defaults
        )
        if created:
            assoc.values.set(AttributeValue.objects.filter(pk__in=assigned_values))


def assign_attributes_to_pages(page_attributes):
    for value in page_attributes:
        pk = value["pk"]
        defaults = value["fields"]
        defaults["page_id"] = defaults.pop("page")
        defaults["assignment_id"] = defaults.pop("assignment")
        assigned_values = defaults.pop("values")
        assoc, created = AssignedPageAttribute.objects.update_or_create(
            pk=pk, defaults=defaults
        )
        if created:
            assoc.values.set(AttributeValue.objects.filter(pk__in=assigned_values))


def set_field_as_money(defaults, field):
    amount_field = f"{field}_amount"
    if amount_field in defaults and defaults[amount_field] is not None:
        defaults[field] = Money(defaults[amount_field], settings.DEFAULT_CURRENCY)


def create_rooms_by_schema(placeholder_dir, create_images):
    path = os.path.join(
        settings.PROJECT_ROOT, "vanphong", "static", "populatedb_data.json"
    )
    with open(path) as f:
        db_items = json.load(f)
    types = defaultdict(list)
    # Sort db objects by its model
    for item in db_items:
        model = item.pop("model")
        types[model].append(item)

    create_room_types(room_type_data=types["room.roomtype"])
    create_categories(
        categories_data=types["room.category"], placeholder_dir=placeholder_dir
    )
    create_attributes(attributes_data=types["attribute.attribute"])
    create_attributes_values(values_data=types["attribute.attributevalue"])
    create_rooms(
        rooms_data=types["room.room"],
        placeholder_dir=placeholder_dir,
        create_images=create_images,
    )
    create_room_channel_listings(
        room_channel_listings_data=types["room.roomchannellisting"],
    )
    create_room_variants(
        variants_data=types["room.roomvariant"], create_images=create_images
    )
    create_room_variant_channel_listings(
        room_variant_channel_listings_data=types[
            "room.roomvariantchannellisting"
        ],
    )
    assign_attributes_to_room_types(
        AttributeRoom, attributes=types["attribute.attributeroom"]
    )
    assign_attributes_to_room_types(
        AttributeVariant, attributes=types["attribute.attributevariant"]
    )
    assign_attributes_to_page_types(
        AttributePage, attributes=types["attribute.attributepage"]
    )
    assign_attributes_to_rooms(
        room_attributes=types["attribute.assignedroomattribute"]
    )
    assign_attributes_to_variants(
        variant_attributes=types["attribute.assignedvariantattribute"]
    )
    assign_attributes_to_pages(page_attributes=types["attribute.assignedpageattribute"])
    create_collections(
        data=types["room.collection"], placeholder_dir=placeholder_dir
    )
    create_collection_channel_listings(
        collection_channel_listings_data=types["room.collectionchannellisting"],
    )
    assign_rooms_to_collections(associations=types["room.collectionroom"])


def create_places_by_schema():
    path = os.path.join(
        settings.PROJECT_ROOT, "vanphong", "static", "populatedb_place.json"
    )
    with open(path, encoding='utf-8') as f:
        db_items = json.load(f)
    types = defaultdict(list)
    # Sort db objects by its model
    for item in db_items:
        model = item.pop("model")
        types[model].append(item)

    for place in types["place.place"]:
        pk = place["pk"]
        defaults = place["fields"]
        Place.objects.update_or_create(pk=pk, defaults=defaults)


class SaleorProvider(BaseProvider):
    def money(self):
        return Money(fake.pydecimal(2, 2, positive=True), settings.DEFAULT_CURRENCY)

    def weight(self):
        return Weight(kg=fake.pydecimal(1, 2, positive=True))


fake.add_provider(SaleorProvider)


def get_email(first_name, last_name):
    _first = unicodedata.normalize("NFD", first_name).encode("ascii", "ignore")
    _last = unicodedata.normalize("NFD", last_name).encode("ascii", "ignore")
    return "%s.%s@example.com" % (
        _first.lower().decode("utf-8"),
        _last.lower().decode("utf-8"),
    )


def create_room_image(room, placeholder_dir, image_name):
    image = get_image(placeholder_dir, image_name)
    # We don't want to create duplicated room images
    if room.images.count() >= len(IMAGES_MAPPING.get(room.pk, [])):
        return None
    room_image = RoomImage(room=room, image=image)
    room_image.save()
    create_room_thumbnails.delay(room_image.pk)
    return room_image


def create_address(save=True):
    address = Address(
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        street_address_1=fake.street_address(),
        city=fake.city(),
        country=settings.DEFAULT_COUNTRY,
    )

    if address.country == "US":
        state = fake.state_abbr()
        address.country_area = state
        address.postal_code = fake.postalcode_in_state(state)
    else:
        address.postal_code = fake.postalcode()

    if save:
        address.save()
    return address


def create_fake_user(save=True):
    address = create_address(save=save)
    email = get_email(address.first_name, address.last_name)

    # Skip the email if it already exists
    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        pass

    user = User(
        first_name=address.first_name,
        last_name=address.last_name,
        email=email,
        password="password",
        default_billing_address=address,
        default_shipping_address=address,
        is_active=True,
        note=fake.paragraph(),
        date_joined=fake.date_time(tzinfo=timezone.get_current_timezone()),
    )

    if save:
        user.save()
        user.addresses.add(address)
    return user


# We don't want to spam the console with payment confirmations sent to
# fake customers.
@patch("vanphong.order.emails.send_payment_confirmation.delay")
def create_fake_payment(mock_email_confirmation, order):
    payment = create_payment(
        gateway="mirumee.payments.dummy",
        customer_ip_address=fake.ipv4(),
        email=order.user_email,
        order=order,
        payment_token=str(uuid.uuid4()),
        total=order.total.gross.amount,
        currency=order.total.gross.currency,
    )

    # Create authorization transaction
    gateway.authorize(payment, payment.token)
    # 20% chance to void the transaction at this stage
    if random.choice([0, 0, 0, 0, 1]):
        gateway.void(payment)
        return payment
    # 25% to end the payment at the authorization stage
    if not random.choice([1, 1, 1, 0]):
        return payment
    # Create capture transaction
    gateway.capture(payment)
    # 25% to refund the payment
    if random.choice([0, 0, 0, 1]):
        gateway.refund(payment)
    return payment


def create_order_lines(order, discounts, how_many=10):
    channel = order.channel
    available_variant_ids = channel.variant_listings.values_list(
        "variant_id", flat=True
    )
    variants = (
        RoomVariant.objects.filter(pk__in=available_variant_ids)
        .order_by("?")
        .prefetch_related("room__room_type")[:how_many]
    )
    variants_iter = itertools.cycle(variants)
    lines = []
    for _ in range(how_many):
        variant = next(variants_iter)
        variant_channel_listing = variant.channel_listings.get(channel=channel)
        room = variant.room
        quantity = random.randrange(1, 5)
        unit_price = variant.get_price(
            room,
            room.collections.all(),
            channel,
            variant_channel_listing,
            discounts,
        )
        unit_price = TaxedMoney(net=unit_price, gross=unit_price)
        total_price = unit_price * quantity
        lines.append(
            OrderLine(
                order=order,
                room_name=str(room),
                variant_name=str(variant),
                room_sku=variant.sku,
                is_shipping_required=variant.is_shipping_required(),
                quantity=quantity,
                variant=variant,
                unit_price=unit_price,
                total_price=total_price,
                tax_rate=0,
            )
        )
    lines = OrderLine.objects.bulk_create(lines)
    manager = get_plugins_manager()
    country = order.shipping_method.shipping_zone.countries[0]
    hotels = Hotel.objects.filter(
        shipping_zones__countries__contains=country
    ).order_by("?")
    hotel_iter = itertools.cycle(hotels)
    for line in lines:
        unit_price = manager.calculate_order_line_unit(line)
        line.unit_price = unit_price
        line.tax_rate = unit_price.tax / unit_price.net
        hotel = next(hotel_iter)
        increase_stock(line, hotel, line.quantity, allocate=True)
    OrderLine.objects.bulk_update(
        lines,
        ["unit_price_net_amount", "unit_price_gross_amount", "currency", "tax_rate"],
    )
    return lines


def create_fulfillments(order):
    for line in order:
        if random.choice([False, True]):
            fulfillment, _ = Fulfillment.objects.get_or_create(order=order)
            quantity = random.randrange(0, line.quantity) + 1
            allocation = line.allocations.get()
            fulfillment.lines.create(
                order_line=line, quantity=quantity, stock=allocation.stock
            )
            line.quantity_fulfilled = quantity
            line.save(update_fields=["quantity_fulfilled"])

            allocation.quantity_allocated = F("quantity_allocated") - quantity
            allocation.save(update_fields=["quantity_allocated"])

    update_order_status(order)


def create_fake_order(discounts, max_order_lines=5):
    channel = Channel.objects.all().order_by("?").first()
    customers = (
        User.objects.filter(is_superuser=False)
        .exclude(default_billing_address=None)
        .order_by("?")
    )
    customer = random.choice([None, customers.first()])

    # 20% chance to be unconfirmed order.
    will_be_unconfirmed = random.choice([0, 0, 0, 0, 1])

    if customer:
        address = customer.default_shipping_address
        order_data = {
            "user": customer,
            "billing_address": customer.default_billing_address,
            "shipping_address": address,
        }
    else:
        address = create_address()
        order_data = {
            "billing_address": address,
            "shipping_address": address,
            "user_email": get_email(address.first_name, address.last_name),
        }

    manager = get_plugins_manager()
    shipping_method_chanel_listing = (
        ShippingMethodChannelListing.objects.filter(channel=channel)
        .order_by("?")
        .first()
    )
    shipping_method = shipping_method_chanel_listing.shipping_method
    shipping_price = shipping_method_chanel_listing.price
    shipping_price = manager.apply_taxes_to_shipping(shipping_price, address)
    order_data.update(
        {
            "channel": channel,
            "shipping_method": shipping_method,
            "shipping_method_name": shipping_method.name,
            "shipping_price": shipping_price,
        }
    )
    if will_be_unconfirmed:
        order_data["status"] = OrderStatus.UNCONFIRMED

    order = Order.objects.create(**order_data)
    lines = create_order_lines(order, discounts, random.randrange(1, max_order_lines))
    order.total = sum([line.total_price for line in lines], shipping_price)
    """
    weight = Weight(kg=0)
    for line in order:
        weight += line.variant.get_weight()
    order.weight = weight
    """
    order.save()

    create_fake_payment(order=order)

    if not will_be_unconfirmed:
        create_fulfillments(order)

    return order


def create_fake_sale():
    sale = Sale.objects.create(
        name="Happy %s day!" % fake.word(),
        type=DiscountValueType.PERCENTAGE,
    )
    for channel in Channel.objects.all():
        SaleChannelListing.objects.create(
            channel=channel,
            currency=channel.currency_code,
            sale=sale,
            discount_value=random.choice([10, 20, 30, 40, 50]),
        )
    for room in Room.objects.all().order_by("?")[:4]:
        sale.rooms.add(room)
    return sale


def create_users(how_many=10):
    for dummy in range(how_many):
        user = create_fake_user()
        yield "User: %s" % (user.email,)


def create_permission_groups():
    super_users = User.objects.filter(is_superuser=True)
    if not super_users:
        super_users = create_staff_users(1, True)
    group = create_group("Full Access", get_permissions(), super_users)
    yield f"Group: {group}"

    staff_users = create_staff_users()
    customer_support_codenames = [
        perm.codename
        for enum in [CheckoutPermissions, OrderPermissions, GiftcardPermissions]
        for perm in enum
    ]
    customer_support_codenames.append(AccountPermissions.MANAGE_USERS.codename)
    customer_support_permissions = Permission.objects.filter(
        codename__in=customer_support_codenames
    )
    group = create_group("Customer Support", customer_support_permissions, staff_users)
    yield f"Group: {group}"


def create_staffs():
    for permission in get_permissions():
        base_name = permission.codename.split("_")[1:]

        group_name = " ".join(base_name)
        group_name += " management"
        group_name = group_name.capitalize()

        email_base_name = [name[:-1] if name[-1] == "s" else name for name in base_name]
        user_email = ".".join(email_base_name)
        user_email += ".manager@example.com"

        user = _create_staff_user(email=user_email)
        group = create_group(group_name, [permission], [user])

        yield f"Group: {group}"
        yield f"User: {user}"


def create_group(name, permissions, users):
    group, _ = Group.objects.get_or_create(name=name)
    group.permissions.add(*permissions)
    group.user_set.add(*users)
    return group


def _create_staff_user(email=None, superuser=False):
    user = User.objects.filter(email=email).first()
    if user:
        return user
    address = create_address()
    first_name = address.first_name
    last_name = address.last_name
    if not email:
        email = get_email(first_name, last_name)

    staff_user = User.objects.create_user(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password=DUMMY_STAFF_PASSWORD,
        default_billing_address=address,
        default_shipping_address=address,
        is_staff=True,
        is_active=True,
        is_superuser=superuser,
    )
    return staff_user


def create_staff_users(how_many=2, superuser=False):
    users = []
    for _ in range(how_many):
        staff_user = _create_staff_user(superuser)
        users.append(staff_user)
    return users


def create_orders(how_many=10):
    discounts = fetch_discounts(timezone.now())
    for _ in range(how_many):
        order = create_fake_order(discounts)
        yield "Order: %s" % (order,)


def create_room_sales(how_many=5):
    for dummy in range(how_many):
        sale = create_fake_sale()
        update_rooms_discounted_prices_of_discount_task.delay(sale.pk)
        yield "Sale: %s" % (sale,)


def create_channel(channel_name, currency_code, slug=None):
    if not slug:
        slug = slugify(channel_name)
    channel, _ = Channel.objects.get_or_create(
        slug=slug,
        defaults={
            "name": channel_name,
            "currency_code": currency_code,
            "is_active": True,
        },
    )
    return f"Channel: {channel}"


def create_channels():
    yield create_channel(
        channel_name="Channel-USD",
        currency_code="USD",
        slug=settings.DEFAULT_CHANNEL_SLUG,
    )
    yield create_channel(
        channel_name="Channel-PLN",
        currency_code="PLN",
    )


def create_shipping_zone(shipping_methods_names, countries, shipping_zone_name):
    shipping_zone = ShippingZone.objects.get_or_create(
        name=shipping_zone_name, defaults={"countries": countries}
    )[0]
    shipping_methods = ShippingMethod.objects.bulk_create(
        [
            ShippingMethod(
                name=name,
                shipping_zone=shipping_zone,
                type=(
                    ShippingMethodType.PRICE_BASED
                    # if random.randint(0, 1)
                    # else ShippingMethodType.WEIGHT_BASED
                ),
                # minimum_order_weight=0,
                # maximum_order_weight=None,
            )
            for name in shipping_methods_names
        ]
    )
    for channel in Channel.objects.all():
        ShippingMethodChannelListing.objects.bulk_create(
            [
                ShippingMethodChannelListing(
                    shipping_method=shipping_method,
                    price_amount=fake.money().amount,
                    minimum_order_price_amount=Decimal(0),
                    maximum_order_price_amount=None,
                    channel=channel,
                    currency=channel.currency_code,
                )
                for shipping_method in shipping_methods
            ]
        )
    return "Shipping Zone: %s" % shipping_zone


def create_shipping_zones():
    european_countries = [
        "AX",
        "AL",
        "AD",
        "AT",
        "BY",
        "BE",
        "BA",
        "BG",
        "HR",
        "CZ",
        "DK",
        "EE",
        "FO",
        "FI",
        "FR",
        "DE",
        "GI",
        "GR",
        "GG",
        "VA",
        "HU",
        "IS",
        "IE",
        "IM",
        "IT",
        "JE",
        "LV",
        "LI",
        "LT",
        "LU",
        "MK",
        "MT",
        "MD",
        "MC",
        "ME",
        "NL",
        "NO",
        "PL",
        "PT",
        "RO",
        "RU",
        "SM",
        "RS",
        "SK",
        "SI",
        "ES",
        "SJ",
        "SE",
        "CH",
        "UA",
        "GB",
    ]
    yield create_shipping_zone(
        shipping_zone_name="Europe",
        countries=european_countries,
        shipping_methods_names=["DHL", "UPS", "Registered priority", "DB Schenker"],
    )
    oceanian_countries = [
        "AS",
        "AU",
        "CX",
        "CC",
        "CK",
        "FJ",
        "PF",
        "GU",
        "HM",
        "KI",
        "MH",
        "FM",
        "NR",
        "NC",
        "NZ",
        "NU",
        "NF",
        "MP",
        "PW",
        "PG",
        "PN",
        "WS",
        "SB",
        "TK",
        "TO",
        "TV",
        "UM",
        "VU",
        "WF",
    ]
    yield create_shipping_zone(
        shipping_zone_name="Oceania",
        countries=oceanian_countries,
        shipping_methods_names=["FBA", "FedEx Express", "Oceania Air Mail"],
    )
    asian_countries = [
        "AF",
        "AM",
        "AZ",
        "BH",
        "BD",
        "BT",
        "BN",
        "KH",
        "CN",
        "CY",
        "GE",
        "HK",
        "IN",
        "ID",
        "IR",
        "IQ",
        "IL",
        "JP",
        "JO",
        "KZ",
        "KP",
        "KR",
        "KW",
        "KG",
        "LA",
        "LB",
        "MO",
        "MY",
        "MV",
        "MN",
        "MM",
        "NP",
        "OM",
        "PK",
        "PS",
        "PH",
        "QA",
        "SA",
        "SG",
        "LK",
        "SY",
        "TW",
        "TJ",
        "TH",
        "TL",
        "TR",
        "TM",
        "AE",
        "UZ",
        "VN",
        "YE",
    ]
    yield create_shipping_zone(
        shipping_zone_name="Asia",
        countries=asian_countries,
        shipping_methods_names=["China Post", "TNT", "Aramex", "EMS"],
    )
    american_countries = [
        "AI",
        "AG",
        "AR",
        "AW",
        "BS",
        "BB",
        "BZ",
        "BM",
        "BO",
        "BQ",
        "BV",
        "BR",
        "CA",
        "KY",
        "CL",
        "CO",
        "CR",
        "CU",
        "CW",
        "DM",
        "DO",
        "EC",
        "SV",
        "FK",
        "GF",
        "GL",
        "GD",
        "GP",
        "GT",
        "GY",
        "HT",
        "HN",
        "JM",
        "MQ",
        "MX",
        "MS",
        "NI",
        "PA",
        "PY",
        "PE",
        "PR",
        "BL",
        "KN",
        "LC",
        "MF",
        "PM",
        "VC",
        "SX",
        "GS",
        "SR",
        "TT",
        "TC",
        "US",
        "UY",
        "VE",
        "VG",
        "VI",
    ]
    yield create_shipping_zone(
        shipping_zone_name="Americas",
        countries=american_countries,
        shipping_methods_names=["DHL", "UPS", "FedEx", "EMS"],
    )
    african_countries = [
        "DZ",
        "AO",
        "BJ",
        "BW",
        "IO",
        "BF",
        "BI",
        "CV",
        "CM",
        "CF",
        "TD",
        "KM",
        "CG",
        "CD",
        "CI",
        "DJ",
        "EG",
        "GQ",
        "ER",
        "SZ",
        "ET",
        "TF",
        "GA",
        "GM",
        "GH",
        "GN",
        "GW",
        "KE",
        "LS",
        "LR",
        "LY",
        "MG",
        "MW",
        "ML",
        "MR",
        "MU",
        "YT",
        "MA",
        "MZ",
        "NA",
        "NE",
        "NG",
        "RE",
        "RW",
        "SH",
        "ST",
        "SN",
        "SC",
        "SL",
        "SO",
        "ZA",
        "SS",
        "SD",
        "TZ",
        "TG",
        "TN",
        "UG",
        "EH",
        "ZM",
        "ZW",
    ]
    yield create_shipping_zone(
        shipping_zone_name="Africa",
        countries=african_countries,
        shipping_methods_names=[
            "Royale International",
            "ACE",
            "fastway couriers",
            "Post Office",
        ],
    )


def create_hotels():
    for shipping_zone in ShippingZone.objects.all():
        shipping_zone_name = shipping_zone.name
        hotel, _ = Hotel.objects.update_or_create(
            name=shipping_zone_name,
            slug=slugify(shipping_zone_name),
            defaults={"company_name": fake.company(), "address": create_address()},
        )
        hotel.shipping_zones.add(shipping_zone)


def create_vouchers():
    channels = list(Channel.objects.all())
    voucher, created = Voucher.objects.get_or_create(
        code="FREESHIPPING",
        defaults={
            "type": VoucherType.SHIPPING,
            "name": "Free shipping",
            "discount_value_type": DiscountValueType.PERCENTAGE,
        },
    )
    for channel in channels:
        VoucherChannelListing.objects.get_or_create(
            voucher=voucher,
            channel=channel,
            defaults={"discount_value": 100, "currency": channel.currency_code},
        )
    if created:
        yield "Voucher #%d" % voucher.id
    else:
        yield "Shipping voucher already exists"

    voucher, created = Voucher.objects.get_or_create(
        code="DISCOUNT",
        defaults={
            "type": VoucherType.ENTIRE_ORDER,
            "name": "Big order discount",
            "discount_value_type": DiscountValueType.FIXED,
        },
    )
    for channel in channels:
        discount_value = 25
        min_spent_amount = 200
        if channel.currency_code == "PLN":
            min_spent_amount *= 4
            discount_value *= 4
        VoucherChannelListing.objects.get_or_create(
            voucher=voucher,
            channel=channel,
            defaults={
                "discount_value": discount_value,
                "currency": channel.currency_code,
                "min_spent_amount": 200,
            },
        )
    if created:
        yield "Voucher #%d" % voucher.id
    else:
        yield "Value voucher already exists"

    voucher, created = Voucher.objects.get_or_create(
        code="VCO9KV98LC",
        defaults={
            "type": VoucherType.ENTIRE_ORDER,
            "discount_value_type": DiscountValueType.PERCENTAGE,
        },
    )
    for channel in channels:
        VoucherChannelListing.objects.get_or_create(
            voucher=voucher,
            channel=channel,
            defaults={"discount_value": 5, "currency": channel.currency_code},
        )
    if created:
        yield "Voucher #%d" % voucher.id
    else:
        yield "Value voucher already exists"


def create_gift_card():
    user = random.choice(
        [User.objects.filter(is_superuser=False).order_by("?").first()]
    )
    gift_card, created = GiftCard.objects.get_or_create(
        code="Gift_card_10",
        defaults={
            "user": user,
            "initial_balance": Money(10, settings.DEFAULT_CURRENCY),
            "current_balance": Money(10, settings.DEFAULT_CURRENCY),
        },
    )
    if created:
        yield "Gift card #%d" % gift_card.id
    else:
        yield "Gift card already exists"


def add_address_to_admin(email):
    address = create_address()
    user = User.objects.get(email=email)
    store_user_address(user, address, AddressType.BILLING)
    store_user_address(user, address, AddressType.SHIPPING)


def create_page_type():
    data = [
        {
            "pk": 1,
            "fields": {
                "private_metadata": {},
                "metadata": {},
                "name": "About",
                "slug": "about",
            },
        },
        {
            "pk": 2,
            "fields": {
                "private_metadata": {},
                "metadata": {},
                "name": "Mission",
                "slug": "mission",
            },
        },
        {
            "pk": 3,
            "fields": {
                "private_metadata": {},
                "metadata": {},
                "name": "Room details",
                "slug": "room-details",
            },
        },
    ]
    for page_type_data in data:
        pk = page_type_data.pop("pk")
        page_type, _ = PageType.objects.update_or_create(
            pk=pk, **page_type_data["fields"]
        )
        yield "Page type %s created" % page_type.slug


def create_pages():
    data_pages = {
        1: {
            "title": "About",
            "slug": "about",
            "page_type_id": 1,
            "content": """
                <h2>E-commerce for the PWA era</h2>
                <h3>A modular, high performance e-commerce storefront built
                with GraphQL, Django, and ReactJS.</h3>
                <p>Saleor is a rapidly-growing open source e-commerce platform that
                has served high-volume companies from branches like publishing
                and apparel since 2012. Based on Python and Django, the latest major
                update introduces a modular front end with a GraphQL API and storefront
                and dashboard written in React to make Saleor a full-functionality
                open source e-commerce.</p>
                <p><a href="https://github.com/mirumee/vanphong">Get Saleor today!</a></p>
                """,
            "content_json": {
                "blocks": [
                    {
                        "data": {"text": "E-commerce for the PWA era", "level": 2},
                        "type": "header",
                    },
                    {
                        "data": {
                            "text": (
                                "A modular, high performance e-commerce storefront "
                                "built with GraphQL, Django, and ReactJS."
                            ),
                            "level": 2,
                        },
                        "type": "header",
                    },
                    {"data": {"text": ""}, "type": "paragraph"},
                    {
                        "data": {
                            "text": (
                                "Saleor is a rapidly-growing open source e-commerce "
                                "platform that has served high-volume companies "
                                "from branches like publishing and apparel since 2012. "
                                "Based on Python and Django, the latest major update "
                                "introduces a modular front end with a GraphQL API "
                                "and storefront and dashboard written in React "
                                "to make Saleor a full-functionality "
                                "open source e-commerce."
                            )
                        },
                        "type": "paragraph",
                    },
                    {"data": {"text": ""}, "type": "paragraph"},
                    {
                        "data": {
                            "text": (
                                '<a href="https://github.com/mirumee/vanphong">'
                                "Get Saleor today!</a>"
                            )
                        },
                        "type": "paragraph",
                    },
                ],
            },
        },
        2: {
            "title": "Apple juice details",
            "slug": "apple-juice-details",
            "page_type_id": 3,
            "content": (
                "\n<h2>Apple juice details</h2>\n"
                "<p>This is example room details page.</p>\n"
            ),
            "content_json": {
                "blocks": [
                    {
                        "data": {"text": "Apple juice details", "level": 2},
                        "type": "header",
                    },
                    {
                        "data": {"text": "This is example room details page."},
                        "type": "paragraph",
                    },
                ]
            },
        },
    }

    for pk in [1, 2]:
        data = data_pages[pk]
        page_data = {
            "content": data["content"],
            "content_json": data["content_json"],
            "title": data["title"],
            "is_published": True,
            "page_type_id": data["page_type_id"],
        }
        page, _ = Page.objects.get_or_create(
            pk=pk, slug=data["slug"], defaults=page_data
        )
        yield "Page %s created" % page.slug


def generate_menu_items(menu: Menu, category: Category, parent_menu_item):
    menu_item, created = menu.items.get_or_create(
        name=category.name, category=category, parent=parent_menu_item
    )

    if created:
        yield "Created menu item for category %s" % category

    for child in category.get_children():
        for msg in generate_menu_items(menu, child, menu_item):
            yield "\t%s" % msg


def generate_menu_tree(menu):
    categories = (
        Category.tree.get_queryset()
        .filter(
            Q(parent__isnull=True) & Q(rooms__isnull=False)
            | Q(children__rooms__isnull=False)
        )
        .distinct()
    )

    for category in categories:
        for msg in generate_menu_items(menu, category, None):
            yield msg


def create_menus():
    # Create navbar menu with category links
    top_menu, _ = Menu.objects.get_or_create(
        name=settings.DEFAULT_MENUS["top_menu_name"]
    )
    top_menu.items.all().delete()
    yield "Created navbar menu"
    for msg in generate_menu_tree(top_menu):
        yield msg

    # Create footer menu with collections and pages
    bottom_menu, _ = Menu.objects.get_or_create(
        name=settings.DEFAULT_MENUS["bottom_menu_name"]
    )
    bottom_menu.items.all().delete()
    collection = Collection.objects.filter(rooms__isnull=False).order_by("?")[0]
    item, _ = bottom_menu.items.get_or_create(name="Collections", collection=collection)

    for collection in Collection.objects.filter(
        rooms__isnull=False, background_image__isnull=False
    ):
        bottom_menu.items.get_or_create(
            name=collection.name, collection=collection, parent=item
        )

    item_vanphong = bottom_menu.items.get_or_create(name="Saleor", url="/")[0]

    page = Page.objects.order_by("?")[0]
    item_vanphong.children.get_or_create(name=page.title, page=page, menu=bottom_menu)

    api_url = build_absolute_uri(reverse("api"))
    item_vanphong.children.get_or_create(
        name="GraphQL API", url=api_url, menu=bottom_menu
    )

    yield "Created footer menu"
    site = Site.objects.get_current()
    site_settings = site.settings
    site_settings.top_menu = top_menu
    site_settings.bottom_menu = bottom_menu
    site_settings.save()


def get_room_list_images_dir(placeholder_dir):
    room_list_images_dir = os.path.join(placeholder_dir, ROOMS_LIST_DIR)
    return room_list_images_dir


def get_image(image_dir, image_name):
    img_path = os.path.join(image_dir, image_name)
    return File(open(img_path, "rb"), name=image_name)
