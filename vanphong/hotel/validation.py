# type: ignore
# mypy error: https://github.com/typeddjango/django-stubs/issues/222
from ..shipping.models import ShippingZone
from .models import Hotel


def validate_hotel_count(shipping_zones, instance: Hotel) -> bool:
    """Every ShippingZone can be assigned to only one hotel.

    If not there would be issue with automatically selecting stock for operation.
    """

    hotels = set(
        ShippingZone.objects.filter(
            id__in=[shipping_zone.id for shipping_zone in shipping_zones]
        )
        .filter(hotels__isnull=False)
        .values_list("hotels", flat=True)
    )
    if not bool(hotels):
        return True
    if len(hotels) > 1:
        return False
    if instance.id is None:
        return False
    return hotels == {instance.id}
