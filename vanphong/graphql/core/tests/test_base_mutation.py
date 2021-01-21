from enum import Enum
from unittest.mock import Mock

import graphene
import pytest
from django.core.exceptions import ImproperlyConfigured

from ...room import types as room_types
from ..mutations import BaseMutation
from ..types.common import Error


class Mutation(BaseMutation):
    name = graphene.Field(graphene.String)

    class Arguments:
        room_id = graphene.ID(required=True)
        channel = graphene.String()

    class Meta:
        description = "Base mutation"

    @classmethod
    def perform_mutation(cls, _root, info, room_id, channel):
        # Need to mock `app_middleware`
        info.context.app = None

        room = cls.get_node_or_error(
            info, room_id, field="room_id", only_type=room_types.Room
        )
        return Mutation(name=room.name)


class ErrorCodeTest(Enum):
    INVALID = "invalid"


ErrorCodeTest = graphene.Enum.from_enum(ErrorCodeTest)


class ErrorTest(Error):
    code = ErrorCodeTest()


class MutationWithCustomErrors(Mutation):
    class Meta:
        description = "Base mutation with custom errors"
        error_type_class = ErrorTest
        error_type_field = "custom_errors"


class Mutations(graphene.ObjectType):
    test = Mutation.Field()
    test_with_custom_errors = MutationWithCustomErrors.Field()


schema = graphene.Schema(
    mutation=Mutations, types=[room_types.Room, room_types.RoomVariant]
)


def test_mutation_without_description_raises_error():
    with pytest.raises(ImproperlyConfigured):

        class MutationNoDescription(BaseMutation):
            name = graphene.Field(graphene.String)

            class Arguments:
                room_id = graphene.ID(required=True)


TEST_MUTATION = """
    mutation testMutation($roomId: ID!, $channel: String) {
        test(roomId: $roomId, channel: $channel) {
            name
            errors {
                field
                message
            }
        }
    }
"""


def test_resolve_id(room, schema_context, channel_USD):
    room_id = graphene.Node.to_global_id("Room", room.pk)
    variables = {"roomId": room_id, "channel": channel_USD.slug}
    result = schema.execute(
        TEST_MUTATION, variables=variables, context_value=schema_context
    )
    assert not result.errors
    assert result.data["test"]["name"] == room.name


def test_user_error_nonexistent_id(schema_context, channel_USD):
    variables = {"roomId": "not-really", "channel": channel_USD.slug}
    result = schema.execute(
        TEST_MUTATION, variables=variables, context_value=schema_context
    )
    assert not result.errors
    user_errors = result.data["test"]["errors"]
    assert user_errors
    assert user_errors[0]["field"] == "roomId"
    assert user_errors[0]["message"] == "Couldn't resolve to a node: not-really"


def test_mutation_custom_errors_default_value(room, schema_context, channel_USD):
    room_id = graphene.Node.to_global_id("Room", room.pk)
    query = """
        mutation testMutation($roomId: ID!, $channel: String) {
            testWithCustomErrors(roomId: $roomId, channel: $channel) {
                name
                errors {
                    field
                    message
                }
                customErrors {
                    field
                    message
                }
            }
        }
    """
    variables = {"roomId": room_id, "channel": channel_USD.slug}
    result = schema.execute(query, variables=variables, context_value=schema_context)
    assert result.data["testWithCustomErrors"]["errors"] == []
    assert result.data["testWithCustomErrors"]["customErrors"] == []


def test_user_error_id_of_different_type(room, schema_context, channel_USD):
    # Test that get_node_or_error checks that the returned ID must be of
    # proper type. Providing correct ID but of different type than expected
    # should result in user error.
    variant = room.variants.first()
    variant_id = graphene.Node.to_global_id("RoomVariant", variant.pk)

    variables = {"roomId": variant_id, "channel": channel_USD.slug}
    result = schema.execute(
        TEST_MUTATION, variables=variables, context_value=schema_context
    )
    assert not result.errors
    user_errors = result.data["test"]["errors"]
    assert user_errors
    assert user_errors[0]["field"] == "roomId"
    assert user_errors[0]["message"] == "Must receive a Room id"


def test_get_node_or_error_returns_null_for_empty_id():
    info = Mock()
    response = Mutation.get_node_or_error(info, "", field="")
    assert response is None
