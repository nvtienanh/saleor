from tempfile import NamedTemporaryFile
from typing import IO, TYPE_CHECKING, Any, Dict, List, Set, Union

import petl as etl
from django.utils import timezone

from ...room.models import Room
from .. import FileTypes
from ..emails import send_email_with_link_to_download_file
from .room_headers import get_export_fields_and_headers_info
from .rooms_data import get_rooms_data

if TYPE_CHECKING:
    # flake8: noqa
    from django.db.models import QuerySet

    from ..models import ExportFile


BATCH_SIZE = 10000


def export_rooms(
    export_file: "ExportFile",
    scope: Dict[str, Union[str, dict]],
    export_info: Dict[str, list],
    file_type: str,
    delimiter: str = ";",
):
    file_name = get_filename("room", file_type)
    queryset = get_room_queryset(scope)

    export_fields, file_headers, data_headers = get_export_fields_and_headers_info(
        export_info
    )

    temporary_file = create_file_with_headers(file_headers, delimiter, file_type)

    export_rooms_in_batches(
        queryset,
        export_info,
        set(export_fields),
        data_headers,
        delimiter,
        temporary_file,
        file_type,
    )

    save_csv_file_in_export_file(export_file, temporary_file, file_name)
    temporary_file.close()

    if export_file.user:
        send_email_with_link_to_download_file(
            export_file, export_file.user.email, "export_rooms_success"
        )


def get_filename(model_name: str, file_type: str) -> str:
    return "{}_data_{}.{}".format(
        model_name, timezone.now().strftime("%d_%m_%Y"), file_type
    )


def get_room_queryset(scope: Dict[str, Union[str, dict]]) -> "QuerySet":
    """Get room queryset based on a scope."""

    from ...graphql.room.filters import RoomFilter

    queryset = Room.objects.all()
    if "ids" in scope:
        queryset = Room.objects.filter(pk__in=scope["ids"])
    elif "filter" in scope:
        queryset = RoomFilter(data=scope["filter"], queryset=queryset).qs

    queryset = queryset.order_by("pk")

    return queryset


def queryset_in_batches(queryset):
    """Slice a queryset into batches.

    Input queryset should be sorted be pk.
    """
    start_pk = 0

    while True:
        qs = queryset.filter(pk__gt=start_pk)[:BATCH_SIZE]
        pks = list(qs.values_list("pk", flat=True))

        if not pks:
            break

        yield pks

        start_pk = pks[-1]


def export_rooms_in_batches(
    queryset: "QuerySet",
    export_info: Dict[str, list],
    export_fields: Set[str],
    headers: List[str],
    delimiter: str,
    temporary_file: Any,
    file_type: str,
):
    hotels = export_info.get("hotels")
    attributes = export_info.get("attributes")
    channels = export_info.get("channels")

    for batch_pks in queryset_in_batches(queryset):
        room_batch = Room.objects.filter(pk__in=batch_pks).prefetch_related(
            "attributes",
            "variants",
            "collections",
            "images",
            "room_type",
            "category",
        )

        export_data = get_rooms_data(
            room_batch, export_fields, attributes, hotels, channels
        )

        append_to_file(export_data, headers, temporary_file, file_type, delimiter)


def create_file_with_headers(file_headers: List[str], delimiter: str, file_type: str):
    table = etl.wrap([file_headers])

    if file_type == FileTypes.CSV:
        temp_file = NamedTemporaryFile("ab+", suffix=".csv")
        etl.tocsv(table, temp_file.name, delimiter=delimiter)
    else:
        temp_file = NamedTemporaryFile("ab+", suffix=".xlsx")
        etl.io.xlsx.toxlsx(table, temp_file.name)

    return temp_file


def append_to_file(
    export_data: List[Dict[str, Union[str, bool]]],
    headers: List[str],
    temporary_file: Any,
    file_type: str,
    delimiter: str,
):
    table = etl.fromdicts(export_data, header=headers, missing=" ")

    if file_type == FileTypes.CSV:
        etl.io.csv.appendcsv(table, temporary_file.name, delimiter=delimiter)
    else:
        etl.io.xlsx.appendxlsx(table, temporary_file.name)


def save_csv_file_in_export_file(
    export_file: "ExportFile", temporary_file: IO[bytes], file_name: str
):
    export_file.content_file.save(file_name, temporary_file)
