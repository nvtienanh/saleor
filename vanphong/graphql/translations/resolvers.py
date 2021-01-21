from ...attribute import models as attribute_models
from ...discount import models as discount_models
from ...room import models as room_models
from ...shipping import models as shipping_models


def resolve_translation(instance, _info, language_code):
    """Get translation object from instance based on language code."""
    return instance.translations.filter(language_code=language_code).first()


def resolve_shipping_methods(info):
    return shipping_models.ShippingMethod.objects.all()


def resolve_attribute_values(info):
    return attribute_models.AttributeValue.objects.all()


def resolve_rooms(_info):
    return room_models.Room.objects.all()


def resolve_room_variants(_info):
    return room_models.RoomVariant.objects.all()


def resolve_sales(_info):
    return discount_models.Sale.objects.all()


def resolve_vouchers(_info):
    return discount_models.Voucher.objects.all()


def resolve_collections(_info):
    return room_models.Collection.objects.all()
