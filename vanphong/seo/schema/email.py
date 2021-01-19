import json
from typing import TYPE_CHECKING

from django.contrib.sites.models import Site

from ...core.utils import build_absolute_uri
from ...core.utils.json_serializer import HTMLSafeJSON

if TYPE_CHECKING:
    from ...order.models import Order, OrderLine


def get_organization():
    site = Site.objects.get_current()
    return {"@type": "Organization", "name": site.name}


def get_room_data(line: "OrderLine", organization: dict) -> dict:
    gross_room_price = line.total_price.gross
    line_name = str(line)
    if line.translated_room_name:
        line_name = (
            f"{line.translated_room_name} ({line.translated_variant_name})"
            if line.translated_variant_name
            else line.translated_room_name
        )
    room_data = {
        "@type": "Offer",
        "itemOffered": {"@type": "Room", "name": line_name, "sku": line.room_sku},
        "price": gross_room_price.amount,
        "priceCurrency": gross_room_price.currency,
        "eligibleQuantity": {"@type": "QuantitativeValue", "value": line.quantity},
        "seller": organization,
    }

    if not line.variant:
        return {}

    room = line.variant.room
    room_image = room.get_first_image()
    if room_image:
        image = room_image.image
        room_data["itemOffered"]["image"] = build_absolute_uri(location=image.url)
    return room_data


def get_order_confirmation_markup(order: "Order") -> str:
    """Generate schema.org markup for order confirmation e-mail message."""
    organization = get_organization()
    data = {
        "@context": "http://schema.org",
        "@type": "Order",
        "merchant": organization,
        "orderNumber": order.pk,
        "priceCurrency": order.total.gross.currency,
        "price": order.total.gross.amount,
        "acceptedOffer": [],
        "orderStatus": "http://schema.org/OrderProcessing",
        "orderDate": order.created,
    }

    for line in order.lines.all():
        room_data = get_room_data(line=line, organization=organization)
        data["acceptedOffer"].append(room_data)
    return json.dumps(data, cls=HTMLSafeJSON)
