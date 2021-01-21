from typing import Dict, List, Mapping, Union

import graphene
from django.core.exceptions import ValidationError

from ...core.permissions import RoomPermissions
from ...csv import models as csv_models
from ...csv.events import export_started_event
from ...csv.tasks import export_rooms_task
from ..attribute.types import Attribute
from ..channel.types import Channel
from ..core.enums import ExportErrorCode
from ..core.mutations import BaseMutation
from ..core.types.common import ExportError
from ..room.filters import RoomFilterInput
from ..room.types import Room
from ..utils import resolve_global_ids_to_primary_keys
from ..hotel.types import Hotel
from .enums import ExportScope, FileTypeEnum, RoomFieldEnum
from .types import ExportFile


class ExportInfoInput(graphene.InputObjectType):
    attributes = graphene.List(
        graphene.NonNull(graphene.ID),
        description="List of attribute ids witch should be exported.",
    )
    hotels = graphene.List(
        graphene.NonNull(graphene.ID),
        description="List of hotel ids witch should be exported.",
    )
    channels = graphene.List(
        graphene.NonNull(graphene.ID),
        description="List of channels ids which should be exported.",
    )
    fields = graphene.List(
        graphene.NonNull(RoomFieldEnum),
        description="List of room fields witch should be exported.",
    )


class ExportRoomsInput(graphene.InputObjectType):
    scope = ExportScope(
        description="Determine which rooms should be exported.", required=True
    )
    filter = RoomFilterInput(
        description="Filtering options for rooms.", required=False
    )
    ids = graphene.List(
        graphene.NonNull(graphene.ID),
        description="List of rooms IDS to export.",
        required=False,
    )
    export_info = ExportInfoInput(
        description="Input with info about fields which should be exported.",
        required=False,
    )
    file_type = FileTypeEnum(description="Type of exported file.", required=True)


class ExportRooms(BaseMutation):
    export_file = graphene.Field(
        ExportFile,
        description=(
            "The newly created export file job which is responsible for export data."
        ),
    )

    class Arguments:
        input = ExportRoomsInput(
            required=True, description="Fields required to export room data"
        )

    class Meta:
        description = "Export rooms to csv file."
        permissions = (RoomPermissions.MANAGE_ROOMS,)
        error_type_class = ExportError
        error_type_field = "export_errors"

    @classmethod
    def perform_mutation(cls, root, info, **data):
        input = data["input"]
        scope = cls.get_rooms_scope(input)
        export_info = cls.get_export_info(input["export_info"])
        file_type = input["file_type"]

        app = info.context.app
        kwargs = {"app": app} if app else {"user": info.context.user}

        export_file = csv_models.ExportFile.objects.create(**kwargs)
        export_started_event(export_file=export_file, **kwargs)
        export_rooms_task.delay(export_file.pk, scope, export_info, file_type)

        export_file.refresh_from_db()
        return cls(export_file=export_file)

    @classmethod
    def get_rooms_scope(cls, input) -> Mapping[str, Union[list, dict, str]]:
        scope = input["scope"]
        if scope == ExportScope.IDS.value:  # type: ignore
            return cls.clean_ids(input)
        elif scope == ExportScope.FILTER.value:  # type: ignore
            return cls.clean_filter(input)
        return {"all": ""}

    @staticmethod
    def clean_ids(input) -> Dict[str, List[str]]:
        ids = input.get("ids", [])
        if not ids:
            raise ValidationError(
                {
                    "ids": ValidationError(
                        "You must provide at least one room id.",
                        code=ExportErrorCode.REQUIRED.value,
                    )
                }
            )
        _, pks = resolve_global_ids_to_primary_keys(ids, graphene_type=Room)
        return {"ids": pks}

    @staticmethod
    def clean_filter(input) -> Dict[str, dict]:
        filter = input.get("filter")
        if not filter:
            raise ValidationError(
                {
                    "filter": ValidationError(
                        "You must provide filter input.",
                        code=ExportErrorCode.REQUIRED.value,
                    )
                }
            )
        return {"filter": filter}

    @classmethod
    def get_export_info(cls, export_info_input):
        export_info = {}
        fields = export_info_input.get("fields")
        if fields:
            export_info["fields"] = fields

        for field, graphene_type in [
            ("attributes", Attribute),
            ("hotels", Hotel),
            ("channels", Channel),
        ]:
            pks = cls.get_items_pks(field, export_info_input, graphene_type)
            if pks:
                export_info[field] = pks

        return export_info

    @staticmethod
    def get_items_pks(field, export_info_input, graphene_type):
        ids = export_info_input.get(field)
        if not ids:
            return
        _, pks = resolve_global_ids_to_primary_keys(ids, graphene_type=graphene_type)
        return pks
