from enum import Enum


class RoomErrorCode(Enum):
    ALREADY_EXISTS = "already_exists"
    ATTRIBUTE_ALREADY_ASSIGNED = "attribute_already_assigned"
    ATTRIBUTE_CANNOT_BE_ASSIGNED = "attribute_cannot_be_assigned"
    ATTRIBUTE_VARIANTS_DISABLED = "attribute_variants_disabled"
    DUPLICATED_INPUT_ITEM = "duplicated_input_item"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    ROOM_WITHOUT_CATEGORY = "room_without_category"
    NOT_ROOMS_IMAGE = "not_rooms_image"
    NOT_ROOMS_VARIANT = "not_rooms_variant"
    NOT_FOUND = "not_found"
    REQUIRED = "required"
    UNIQUE = "unique"
    VARIANT_NO_DIGITAL_CONTENT = "variant_no_digital_content"
    CANNOT_MANAGE_ROOM_WITHOUT_VARIANT = "cannot_manage_room_without_variant"
    ROOM_NOT_ASSIGNED_TO_CHANNEL = "room_not_assigned_to_channel"


class CollectionErrorCode(Enum):
    DUPLICATED_INPUT_ITEM = "duplicated_input_item"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    REQUIRED = "required"
    UNIQUE = "unique"
    CANNOT_MANAGE_ROOM_WITHOUT_VARIANT = "cannot_manage_room_without_variant"
