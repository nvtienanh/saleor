from enum import Enum


class DiscountErrorCode(Enum):
    ALREADY_EXISTS = "already_exists"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    REQUIRED = "required"
    UNIQUE = "unique"
    CANNOT_MANAGE_ROOM_WITHOUT_VARIANT = "cannot_manage_room_without_variant"
    DUPLICATED_INPUT_ITEM = "duplicated_input_item"
