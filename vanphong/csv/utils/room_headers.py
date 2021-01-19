from collections import ChainMap
from typing import Dict, List, Tuple

from django.db.models import Value as V
from django.db.models.functions import Concat

from ...attribute.models import Attribute
from ...channel.models import Channel
from ...hotel.models import Hotel
from . import RoomExportFields


def get_export_fields_and_headers_info(
    export_info: Dict[str, list]
) -> Tuple[List[str], List[str], List[str]]:
    """Get export fields, all headers and headers mapping.

    Based on export_info returns exported fields, fields to headers mapping and
    all headers.
    Headers contains room, variant, attribute and hotel headers.
    """
    export_fields, file_headers = get_room_export_fields_and_headers(export_info)
    attributes_headers = get_attributes_headers(export_info)
    hotels_headers = get_hotels_headers(export_info)
    channels_headers = get_channels_headers(export_info)

    data_headers = (
        export_fields + attributes_headers + hotels_headers + channels_headers
    )
    file_headers += attributes_headers + hotels_headers + channels_headers
    return export_fields, file_headers, data_headers


def get_room_export_fields_and_headers(
    export_info: Dict[str, list]
) -> Tuple[List[str], List[str]]:
    """Get export fields from export info and prepare headers mapping.

    Based on given fields headers from export info, export fields set and
    headers mapping is prepared.
    """
    export_fields = ["id"]
    file_headers = ["id"]

    fields = export_info.get("fields")
    if not fields:
        return export_fields, file_headers

    fields_mapping = dict(
        ChainMap(
            *reversed(
                RoomExportFields.HEADERS_TO_FIELDS_MAPPING.values()
            )  # type: ignore
        )
    )

    for field in fields:
        lookup_field = fields_mapping[field]
        export_fields.append(lookup_field)
        file_headers.append(field)

    return export_fields, file_headers


def get_attributes_headers(export_info: Dict[str, list]) -> List[str]:
    """Get headers for exported attributes.

    Headers are build from slug and contains information if it's a room or variant
    attribute. Respectively for room: "slug-value (room attribute)"
    and for variant: "slug-value (variant attribute)".
    """

    attribute_ids = export_info.get("attributes")
    if not attribute_ids:
        return []

    attributes = Attribute.objects.filter(pk__in=attribute_ids).order_by("slug")

    rooms_headers = (
        attributes.filter(room_types__isnull=False)
        .annotate(header=Concat("slug", V(" (room attribute)")))
        .values_list("header", flat=True)
    )

    variant_headers = (
        attributes.filter(room_variant_types__isnull=False)
        .annotate(header=Concat("slug", V(" (variant attribute)")))
        .values_list("header", flat=True)
    )

    return list(rooms_headers) + list(variant_headers)


def get_hotels_headers(export_info: Dict[str, list]) -> List[str]:
    """Get headers for exported hotels.

    Headers are build from slug. Example: "slug-value (hotel quantity)"
    """
    hotel_ids = export_info.get("hotels")
    if not hotel_ids:
        return []

    hotels_headers = (
        Hotel.objects.filter(pk__in=hotel_ids)
        .order_by("slug")
        .annotate(header=Concat("slug", V(" (hotel quantity)")))
        .values_list("header", flat=True)
    )

    return list(hotels_headers)


def get_channels_headers(export_info: Dict[str, list]) -> List[str]:
    """Get headers for exported channels.

    Headers are build from slug and exported field.

    Example:
    - currency code data header: "slug-value (channel currency code)"
    - published data header: "slug-value (channel visible)"
    - publication date data header: "slug-value (channel publication date)"

    """
    channel_ids = export_info.get("channels")
    if not channel_ids:
        return []

    channels_slugs = (
        Channel.objects.filter(pk__in=channel_ids)
        .order_by("slug")
        .values_list("slug", flat=True)
    )

    fields = [
        *RoomExportFields.ROOM_CHANNEL_LISTING_FIELDS.keys(),
        *RoomExportFields.VARIANT_CHANNEL_LISTING_FIELDS.keys(),
    ]
    channels_headers = []
    for slug in channels_slugs:
        channels_headers.extend(
            [
                f"{slug} (channel {field.replace('_', ' ')})"
                for field in fields
                if field not in ["slug", "channel_pk"]
            ]
        )

    return list(channels_headers)
