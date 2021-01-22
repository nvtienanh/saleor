from collections import defaultdict, namedtuple
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Union
from urllib.parse import urljoin

from django.conf import settings
from django.db.models import Case, CharField
from django.db.models import Value as V
from django.db.models import When
from django.db.models.functions import Concat

from ...attribute import AttributeInputType
from ...core.utils import build_absolute_uri
from . import RoomExportFields

if TYPE_CHECKING:
    from django.db.models import QuerySet


def get_rooms_data(
    queryset: "QuerySet",
    export_fields: Set[str],
    attribute_ids: Optional[List[int]],
    hotel_ids: Optional[List[int]],
    channel_ids: Optional[List[int]],
) -> List[Dict[str, Union[str, bool]]]:
    """Create data list of rooms and their variants with fields values.

    It return list with room and variant data which can be used as import to
    csv writer and list of attribute and hotel headers.
    """

    rooms_with_variants_data = []

    room_fields = set(
        RoomExportFields.HEADERS_TO_FIELDS_MAPPING["fields"].values()
    )
    room_export_fields = export_fields & room_fields
    room_export_fields.add("variants__id")

    rooms_data = (
        queryset.annotate(
            room_weight=Case(
                When(weight__isnull=False, then=Concat("weight", V(" g"))),
                default=V(""),
                output_field=CharField(),
            ),
            variant_weight=Case(
                When(
                    variants__weight__isnull=False,
                    then=Concat("variants__weight", V(" g")),
                ),
                default=V(""),
                output_field=CharField(),
            ),
        )
        .order_by("pk", "variants__pk")
        .values(*room_export_fields)
        .distinct("pk", "variants__pk")
    )

    rooms_relations_data = get_rooms_relations_data(
        queryset, export_fields, attribute_ids, channel_ids
    )

    variants_relations_data = get_variants_relations_data(
        queryset, export_fields, attribute_ids, hotel_ids, channel_ids
    )

    for room_data in rooms_data:
        pk = room_data["id"]
        variant_pk = room_data.pop("variants__id")

        room_relations_data: Dict[str, str] = rooms_relations_data.get(pk, {})
        variant_relations_data: Dict[str, str] = variants_relations_data.get(
            variant_pk, {}
        )

        data = {**room_data, **room_relations_data, **variant_relations_data}

        rooms_with_variants_data.append(data)

    return rooms_with_variants_data


def get_rooms_relations_data(
    queryset: "QuerySet",
    export_fields: Set[str],
    attribute_ids: Optional[List[int]],
    channel_ids: Optional[List[int]],
) -> Dict[int, Dict[str, str]]:
    """Get data about room relations fields.

    If any many to many fields are in export_fields or some attribute_ids exists then
    dict with room relations fields is returned.
    Otherwise it returns empty dict.
    """
    many_to_many_fields = set(
        RoomExportFields.HEADERS_TO_FIELDS_MAPPING["room_many_to_many"].values()
    )
    relations_fields = export_fields & many_to_many_fields
    if relations_fields or attribute_ids or channel_ids:
        return prepare_rooms_relations_data(
            queryset, relations_fields, attribute_ids, channel_ids
        )

    return {}


def prepare_rooms_relations_data(
    queryset: "QuerySet",
    fields: Set[str],
    attribute_ids: Optional[List[int]],
    channel_ids: Optional[List[int]],
) -> Dict[int, Dict[str, str]]:
    """Prepare data about rooms relation fields for given queryset.

    It return dict where key is a room pk, value is a dict with relation fields data.
    """
    attribute_fields = RoomExportFields.ROOM_ATTRIBUTE_FIELDS
    channel_fields = RoomExportFields.ROOM_CHANNEL_LISTING_FIELDS.copy()
    result_data: Dict[int, dict] = defaultdict(dict)

    fields.add("pk")
    if attribute_ids:
        fields.update(attribute_fields.values())
    if channel_ids:
        fields.update(channel_fields.values())

    relations_data = queryset.values(*fields)

    channel_pk_lookup = channel_fields.pop("channel_pk")
    channel_slug_lookup = channel_fields.pop("slug")

    for data in relations_data.iterator():
        pk = data.get("pk")
        collection = data.get("collections__slug")
        image = data.pop("images__image", None)

        result_data = add_image_uris_to_data(pk, image, "images__image", result_data)
        result_data = add_collection_info_to_data(pk, collection, result_data)

        result_data, data = handle_attribute_data(
            pk, data, attribute_ids, result_data, attribute_fields, "room attribute"
        )
        result_data, data = handle_channel_data(
            pk,
            data,
            channel_ids,
            result_data,
            channel_pk_lookup,
            channel_slug_lookup,
            channel_fields,
        )

    result: Dict[int, Dict[str, str]] = {
        pk: {
            header: ", ".join(sorted(values)) if isinstance(values, set) else values
            for header, values in data.items()
        }
        for pk, data in result_data.items()
    }
    return result


def get_variants_relations_data(
    queryset: "QuerySet",
    export_fields: Set[str],
    attribute_ids: Optional[List[int]],
    hotel_ids: Optional[List[int]],
    channel_ids: Optional[List[int]],
) -> Dict[int, Dict[str, str]]:
    """Get data about variants relations fields.

    If any many to many fields are in export_fields or some attribute_ids or
    hotel_ids exists then dict with variant relations fields is returned.
    Otherwise it returns empty dict.
    """
    many_to_many_fields = set(
        RoomExportFields.HEADERS_TO_FIELDS_MAPPING["variant_many_to_many"].values()
    )
    relations_fields = export_fields & many_to_many_fields
    if relations_fields or attribute_ids or hotel_ids or channel_ids:
        return prepare_variants_relations_data(
            queryset, relations_fields, attribute_ids, hotel_ids, channel_ids
        )

    return {}


def prepare_variants_relations_data(
    queryset: "QuerySet",
    fields: Set[str],
    attribute_ids: Optional[List[int]],
    hotel_ids: Optional[List[int]],
    channel_ids: Optional[List[int]],
) -> Dict[int, Dict[str, str]]:
    """Prepare data about variants relation fields for given queryset.

    It return dict where key is a room pk, value is a dict with relation fields data.
    """
    attribute_fields = RoomExportFields.VARIANT_ATTRIBUTE_FIELDS
    hotel_fields = RoomExportFields.HOTEL_FIELDS
    channel_fields = RoomExportFields.VARIANT_CHANNEL_LISTING_FIELDS.copy()

    result_data: Dict[int, dict] = defaultdict(dict)
    fields.add("variants__pk")

    if attribute_ids:
        fields.update(attribute_fields.values())
    if hotel_ids:
        fields.update(hotel_fields.values())
    if channel_ids:
        fields.update(channel_fields.values())

    relations_data = queryset.values(*fields)

    channel_pk_lookup = channel_fields.pop("channel_pk")
    channel_slug_lookup = channel_fields.pop("slug")

    for data in relations_data.iterator():
        pk = data.get("variants__pk")
        image = data.pop("variants__images__image", None)

        result_data = add_image_uris_to_data(
            pk, image, "variants__images__image", result_data
        )
        result_data, data = handle_attribute_data(
            pk, data, attribute_ids, result_data, attribute_fields, "variant attribute"
        )
        result_data, data = handle_channel_data(
            pk,
            data,
            channel_ids,
            result_data,
            channel_pk_lookup,
            channel_slug_lookup,
            channel_fields,
        )
        result_data, data = handle_hotel_data(
            pk, data, hotel_ids, result_data, hotel_fields
        )

    result: Dict[int, Dict[str, str]] = {
        pk: {
            header: ", ".join(sorted(values)) if isinstance(values, set) else values
            for header, values in data.items()
        }
        for pk, data in result_data.items()
    }
    return result


def add_collection_info_to_data(
    pk: int, collection: str, result_data: Dict[int, dict]
) -> Dict[int, dict]:
    """Add collection info to room data.

    This functions adds info about collection to dict with room data.
    If some collection info already exists in data, collection slug is added
    to set with other values.
    It returns updated room data.
    """

    if collection:
        header = "collections__slug"
        if header in result_data[pk]:
            result_data[pk][header].add(collection)  # type: ignore
        else:
            result_data[pk][header] = {collection}
    return result_data


def add_image_uris_to_data(
    pk: int, image: str, header: str, result_data: Dict[int, dict]
) -> Dict[int, dict]:
    """Add absolute uri of given image path to room or variant data.

    This function based on given image path creates absolute uri and adds it to dict
    with variant or room data. If some info about images already exists in data,
    absolute uri of given image is added to set with other uris.
    """
    if image:
        uri = build_absolute_uri(urljoin(settings.MEDIA_URL, image))
        if header in result_data[pk]:
            result_data[pk][header].add(uri)
        else:
            result_data[pk][header] = {uri}
    return result_data


AttributeData = namedtuple(
    "AttributeData", ["slug", "file_url", "value", "input_type", "entity_type"]
)


def handle_attribute_data(
    pk: int,
    data: dict,
    attribute_ids: Optional[List[int]],
    result_data: Dict[int, dict],
    attribute_fields: dict,
    attribute_owner: str,
):
    attribute_pk = str(data.pop(attribute_fields["attribute_pk"], ""))
    attribute_data = AttributeData(
        slug=data.pop(attribute_fields["slug"], None),
        input_type=data.pop(attribute_fields["input_type"], None),
        file_url=data.pop(attribute_fields["file_url"], None),
        value=data.pop(attribute_fields["value"], None),
        entity_type=data.pop(attribute_fields["entity_type"], None),
    )

    if attribute_ids and attribute_pk in attribute_ids:
        result_data = add_attribute_info_to_data(
            pk, attribute_data, attribute_owner, result_data
        )

    return result_data, data


def handle_channel_data(
    pk: int,
    data: dict,
    channel_ids: Optional[List[int]],
    result_data: Dict[int, dict],
    pk_lookup: str,
    slug_lookup: str,
    fields: dict,
):
    channel_data: dict = {}

    channel_pk = str(data.pop(pk_lookup, ""))
    channel_data = {
        "slug": data.pop(slug_lookup, None),
    }
    for field, lookup in fields.items():
        channel_data[field] = data.pop(lookup, None)

    if channel_ids and channel_pk in channel_ids:
        result_data = add_channel_info_to_data(
            pk, channel_data, result_data, list(fields.keys())
        )

    return result_data, data


def handle_hotel_data(
    pk: int,
    data: dict,
    hotel_ids: Optional[List[int]],
    result_data: Dict[int, dict],
    hotel_fields: dict,
):
    hotel_data: dict = {}

    hotel_pk = str(data.pop(hotel_fields["hotel_pk"], ""))
    hotel_data = {
        "slug": data.pop(hotel_fields["slug"], None),
        "qty": data.pop(hotel_fields["quantity"], None),
    }

    if hotel_ids and hotel_pk in hotel_ids:
        result_data = add_hotel_info_to_data(pk, hotel_data, result_data)

    return result_data, data


def add_attribute_info_to_data(
    pk: int,
    attribute_data: AttributeData,
    attribute_owner: str,
    result_data: Dict[int, dict],
) -> Dict[int, dict]:
    """Add info about attribute to variant or room data.

    This functions adds info about attribute to dict with variant or room data.
    If attribute with given slug already exists in data, attribute value is added
    to set with values.
    It returns updated data.
    """
    slug = attribute_data.slug
    header = None
    if slug:
        header = f"{slug} ({attribute_owner})"
        input_type = attribute_data.input_type
        if input_type == AttributeInputType.FILE:
            value = build_absolute_uri(
                urljoin(settings.MEDIA_URL, attribute_data.file_url)
            )
        elif input_type == AttributeInputType.REFERENCE:
            reference_id = attribute_data.value.split("_")[1]
            value = f"{attribute_data.entity_type}_{reference_id}"
        else:
            value = attribute_data.value
        if header in result_data[pk]:
            result_data[pk][header].add(value)  # type: ignore
        else:
            result_data[pk][header] = {value}
    return result_data


def add_hotel_info_to_data(
    pk: int,
    hotel_data: Dict[str, Union[Optional[str]]],
    result_data: Dict[int, dict],
) -> Dict[int, dict]:
    """Add info about stock quantity to variant data.

    This functions adds info about stock quantity to dict with variant data.
    It returns updated data.
    """

    slug = hotel_data["slug"]
    if slug:
        hotel_qty_header = f"{slug} (hotel quantity)"
        if hotel_qty_header not in result_data[pk]:
            result_data[pk][hotel_qty_header] = hotel_data["qty"]

    return result_data


def add_channel_info_to_data(
    pk: int,
    channel_data: Dict[str, Union[Optional[str]]],
    result_data: Dict[int, dict],
    fields: List[str],
) -> Dict[int, dict]:
    """Add info about channel currency code, whether is published and publication date.

    This functions adds info about channel to dict with room data.
    It returns updated data.
    """
    slug = channel_data["slug"]
    if slug:
        for field in fields:
            header = f"{slug} (channel {field.replace('_', ' ')})"
            if header not in result_data[pk]:
                result_data[pk][header] = channel_data[field]

    return result_data
