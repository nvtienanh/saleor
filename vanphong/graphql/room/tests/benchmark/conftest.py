import pytest

from .....discount.models import Sale, SaleChannelListing
from .....room.models import Category


@pytest.fixture
def sales_list(channel_USD):
    sales = Sale.objects.bulk_create([Sale(name="Sale1"), Sale(name="Sale2")])
    values = [15, 5]
    SaleChannelListing.objects.bulk_create(
        [
            SaleChannelListing(
                sale=sale,
                channel=channel_USD,
                discount_value=values[i],
                currency=channel_USD.currency_code,
            )
            for i, sale in enumerate(sales)
        ]
    )
    return list(sales)


@pytest.fixture
def category_with_rooms(
    room_with_image,
    room_list_published,
    room_with_variant_with_two_attributes,
    room_with_multiple_values_attributes,
    room_without_shipping,
    sales_list,
):
    category = Category.objects.create(name="Category", slug="cat")

    room_list_published.update(category=category)

    room_with_image.category = category
    room_with_image.save()
    room_with_variant_with_two_attributes.category = category
    room_with_variant_with_two_attributes.save()
    room_with_multiple_values_attributes.category = category
    room_with_multiple_values_attributes.save()
    room_without_shipping.category = category
    room_without_shipping.save()

    return category
