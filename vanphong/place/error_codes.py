from enum import Enum


class PlaceErrorCode(str, Enum):
    CANNOT_ASSIGN_NODE = "cannot_assign_node"
    GRAPHQL_ERROR = "graphql_error"
    INVALID = "invalid"
    INVALID_PLACE_ITEM = "invalid_place_item"
    NO_PLACE_ITEM_PROVIDED = "no_item_provided"
    NOT_FOUND = "not_found"
    REQUIRED = "required"
    TOO_MANY_PLACE_ITEMS = "too_many_items"
    UNIQUE = "unique"
