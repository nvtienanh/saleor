from unittest.mock import ANY, patch

import graphene
import pytest

from .....attribute.models import Attribute
from .....channel.models import Channel
from .....csv import ExportEvents
from .....csv.models import ExportEvent
from .....hotel.models import Hotel
from ....tests.utils import get_graphql_content
from ...enums import ExportScope, FileTypeEnum, RoomFieldEnum

EXPORT_ROOMS_MUTATION = """
    mutation ExportRooms($input: ExportRoomsInput!){
        exportRooms(input: $input){
            exportFile {
                id
                status
                createdAt
                updatedAt
                url
                user {
                    email
                }
                app {
                    name
                }
            }
            exportErrors {
                field
                code
                message
            }
        }
    }
"""


@pytest.mark.parametrize(
    "input, called_data",
    [
        (
            {
                "scope": ExportScope.ALL.name,
                "exportInfo": {},
                "fileType": FileTypeEnum.CSV.name,
            },
            {"all": ""},
        ),
        (
            {
                "scope": ExportScope.FILTER.name,
                "filter": {"isPublished": True},
                "exportInfo": {},
                "fileType": FileTypeEnum.CSV.name,
            },
            {"filter": {"is_published": True}},
        ),
    ],
)
@patch("saleor.graphql.csv.mutations.export_rooms_task.delay")
def test_export_rooms_mutation(
    export_rooms_mock,
    staff_api_client,
    room_list,
    permission_manage_rooms,
    permission_manage_apps,
    input,
    called_data,
):
    query = EXPORT_ROOMS_MUTATION
    user = staff_api_client.user
    variables = {"input": input}

    response = staff_api_client.post_graphql(
        query,
        variables=variables,
        permissions=[permission_manage_rooms, permission_manage_apps],
    )
    content = get_graphql_content(response)
    data = content["data"]["exportRooms"]
    export_file_data = data["exportFile"]

    export_rooms_mock.assert_called_once_with(
        ANY, called_data, {}, FileTypeEnum.CSV.value
    )

    assert not data["exportErrors"]
    assert data["exportFile"]["id"]
    assert export_file_data["createdAt"]
    assert export_file_data["user"]["email"] == staff_api_client.user.email
    assert export_file_data["app"] is None
    assert ExportEvent.objects.filter(
        user=user, app=None, type=ExportEvents.EXPORT_PENDING
    ).exists()


@patch("saleor.graphql.csv.mutations.export_rooms_task.delay")
def test_export_rooms_mutation_by_app(
    export_rooms_mock,
    app_api_client,
    room_list,
    permission_manage_rooms,
    permission_manage_apps,
    permission_manage_staff,
):
    query = EXPORT_ROOMS_MUTATION
    app = app_api_client.app
    variables = {
        "input": {
            "scope": ExportScope.ALL.name,
            "exportInfo": {},
            "fileType": FileTypeEnum.CSV.name,
        }
    }

    response = app_api_client.post_graphql(
        query,
        variables=variables,
        permissions=[
            permission_manage_rooms,
            permission_manage_apps,
            permission_manage_staff,
        ],
    )
    content = get_graphql_content(response)
    data = content["data"]["exportRooms"]
    export_file_data = data["exportFile"]

    export_rooms_mock.assert_called_once_with(
        ANY, {"all": ""}, {}, FileTypeEnum.CSV.value
    )

    assert not data["exportErrors"]
    assert data["exportFile"]["id"]
    assert export_file_data["createdAt"]
    assert export_file_data["user"] is None
    assert export_file_data["app"]["name"] == app.name
    assert ExportEvent.objects.filter(
        user=None, app=app, type=ExportEvents.EXPORT_PENDING
    ).exists()


@patch("saleor.graphql.csv.mutations.export_rooms_task.delay")
def test_export_rooms_mutation_ids_scope(
    export_rooms_mock,
    staff_api_client,
    room_list,
    permission_manage_rooms,
    permission_manage_apps,
):
    query = EXPORT_ROOMS_MUTATION
    user = staff_api_client.user

    rooms = room_list[:2]

    ids = []
    pks = set()
    for room in rooms:
        pks.add(str(room.pk))
        ids.append(graphene.Node.to_global_id("Room", room.pk))

    variables = {
        "input": {
            "scope": ExportScope.IDS.name,
            "ids": ids,
            "exportInfo": {
                "fields": [RoomFieldEnum.NAME.name],
                "hotels": [],
                "attributes": [],
            },
            "fileType": FileTypeEnum.XLSX.name,
        }
    }

    response = staff_api_client.post_graphql(
        query,
        variables=variables,
        permissions=[permission_manage_rooms, permission_manage_apps],
    )
    content = get_graphql_content(response)
    data = content["data"]["exportRooms"]
    export_file_data = data["exportFile"]

    export_rooms_mock.assert_called_once()
    (
        call_args,
        call_kwargs,
    ) = export_rooms_mock.call_args

    assert set(call_args[1]["ids"]) == pks
    assert call_args[2] == {"fields": [RoomFieldEnum.NAME.value]}
    assert call_args[3] == FileTypeEnum.XLSX.value

    assert not data["exportErrors"]
    assert data["exportFile"]["id"]
    assert export_file_data["createdAt"]
    assert export_file_data["user"]["email"] == staff_api_client.user.email
    assert export_file_data["app"] is None
    assert ExportEvent.objects.filter(
        user=user, app=None, type=ExportEvents.EXPORT_PENDING
    ).exists()


@patch("saleor.graphql.csv.mutations.export_rooms_task.delay")
def test_export_rooms_mutation_with_hotel_and_attribute_ids(
    export_rooms_mock,
    staff_api_client,
    room_list,
    channel_USD,
    channel_PLN,
    permission_manage_rooms,
    permission_manage_apps,
):
    query = EXPORT_ROOMS_MUTATION
    user = staff_api_client.user

    rooms = room_list[:2]

    ids = []
    pks = set()
    for room in rooms:
        pks.add(str(room.pk))
        ids.append(graphene.Node.to_global_id("Room", room.pk))

    attribute_pks = [str(attr.pk) for attr in Attribute.objects.all()]
    hotel_pks = [str(hotel.pk) for hotel in Hotel.objects.all()]
    channel_pks = [str(channel.pk) for channel in Channel.objects.all()]

    attribute_ids = [
        graphene.Node.to_global_id("Attribute", pk) for pk in attribute_pks
    ]
    hotel_ids = [
        graphene.Node.to_global_id("Hotel", pk) for pk in hotel_pks
    ]
    channel_ids = [graphene.Node.to_global_id("Channel", pk) for pk in channel_pks]

    variables = {
        "input": {
            "scope": ExportScope.IDS.name,
            "ids": ids,
            "exportInfo": {
                "fields": [RoomFieldEnum.NAME.name],
                "hotels": hotel_ids,
                "attributes": attribute_ids,
                "channels": channel_ids,
            },
            "fileType": FileTypeEnum.CSV.name,
        }
    }

    response = staff_api_client.post_graphql(
        query,
        variables=variables,
        permissions=[permission_manage_rooms, permission_manage_apps],
    )
    content = get_graphql_content(response)
    data = content["data"]["exportRooms"]
    export_file_data = data["exportFile"]

    export_rooms_mock.assert_called_once()
    (
        call_args,
        call_kwargs,
    ) = export_rooms_mock.call_args

    assert set(call_args[1]["ids"]) == pks
    assert call_args[2] == {
        "fields": [RoomFieldEnum.NAME.value],
        "hotels": hotel_pks,
        "attributes": attribute_pks,
        "channels": channel_pks,
    }
    assert call_args[3] == FileTypeEnum.CSV.value

    assert not data["exportErrors"]
    assert data["exportFile"]["id"]
    assert export_file_data["createdAt"]
    assert export_file_data["user"]["email"] == staff_api_client.user.email
    assert export_file_data["app"] is None
    assert ExportEvent.objects.filter(
        user=user, app=None, type=ExportEvents.EXPORT_PENDING
    ).exists()


@pytest.mark.parametrize(
    "input, error_field",
    [
        (
            {
                "scope": ExportScope.FILTER.name,
                "exportInfo": {},
                "fileType": FileTypeEnum.CSV.name,
            },
            "filter",
        ),
        (
            {
                "scope": ExportScope.IDS.name,
                "exportInfo": {},
                "fileType": FileTypeEnum.CSV.name,
            },
            "ids",
        ),
    ],
)
@patch("saleor.graphql.csv.mutations.export_rooms_task.delay")
def test_export_rooms_mutation_failed(
    export_rooms_mock,
    staff_api_client,
    room_list,
    permission_manage_rooms,
    input,
    error_field,
):
    query = EXPORT_ROOMS_MUTATION
    user = staff_api_client.user
    variables = {"input": input}

    response = staff_api_client.post_graphql(
        query, variables=variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["exportRooms"]
    errors = data["exportErrors"]

    export_rooms_mock.assert_not_called()

    assert data["exportErrors"]
    assert errors[0]["field"] == error_field
    assert not ExportEvent.objects.filter(
        user=user, type=ExportEvents.EXPORT_PENDING
    ).exists()
