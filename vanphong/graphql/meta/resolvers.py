from operator import itemgetter

from ...account import models as account_models
from ...app import models as app_models
from ...attribute import models as attribute_models
from ...checkout import models as checkout_models
from ...core.exceptions import PermissionDenied
from ...core.models import ModelWithMetadata
from ...order import models as order_models
from ...page import models as page_models
from ...room import models as room_models
from ...shipping import models as shipping_models
from ...hotel import models as hotel_models
from ..utils import get_user_or_app_from_context
from .permissions import PRIVATE_META_PERMISSION_MAP


def resolve_object_with_metadata_type(instance: ModelWithMetadata):
    # Imports inside resolvers to avoid circular imports.
    from ...invoice import models as invoice_models
    from ...menu import models as menu_models
    from ..account import types as account_types
    from ..app import types as app_types
    from ..attribute import types as attribute_types
    from ..checkout import types as checkout_types
    from ..invoice import types as invoice_types
    from ..menu import types as menu_types
    from ..order import types as order_types
    from ..page import types as page_types
    from ..room import types as room_types
    from ..shipping import types as shipping_types
    from ..hotel import types as hotel_types

    MODEL_TO_TYPE_MAP = {
        attribute_models.Attribute: attribute_types.Attribute,
        room_models.Category: room_types.Category,
        checkout_models.Checkout: checkout_types.Checkout,
        room_models.Collection: room_types.Collection,
        room_models.DigitalContent: room_types.DigitalContent,
        order_models.Fulfillment: order_types.Fulfillment,
        order_models.Order: order_types.Order,
        invoice_models.Invoice: invoice_types.Invoice,
        page_models.Page: page_types.Page,
        page_models.PageType: page_types.PageType,
        room_models.Room: room_types.Room,
        room_models.RoomType: room_types.RoomType,
        room_models.RoomVariant: room_types.RoomVariant,
        menu_models.Menu: menu_types.Menu,
        menu_models.MenuItem: menu_types.MenuItem,
        shipping_models.ShippingMethod: shipping_types.ShippingMethod,
        shipping_models.ShippingZone: shipping_types.ShippingZone,
        app_models.App: app_types.App,
        account_models.User: account_types.User,
        hotel_models.Hotel: hotel_types.Hotel,
    }
    return MODEL_TO_TYPE_MAP.get(instance.__class__, None)


def resolve_metadata(metadata: dict):
    return sorted(
        [{"key": k, "value": v} for k, v in metadata.items()],
        key=itemgetter("key"),
    )


def resolve_private_metadata(root: ModelWithMetadata, info):
    item_type = resolve_object_with_metadata_type(root)
    if not item_type:
        raise NotImplementedError(
            f"Model {type(root)} can't be mapped to type with metadata. "
            "Make sure that model exists inside MODEL_TO_TYPE_MAP."
        )

    get_required_permission = PRIVATE_META_PERMISSION_MAP[item_type.__name__]
    if not get_required_permission:
        raise PermissionDenied()

    required_permission = get_required_permission(info, root.pk)
    if not required_permission:
        raise PermissionDenied()

    requester = get_user_or_app_from_context(info.context)
    if not requester.has_perms(required_permission):
        raise PermissionDenied()

    return resolve_metadata(root.private_metadata)
