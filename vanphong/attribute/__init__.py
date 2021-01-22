class AttributeInputType:
    """The type that we expect to render the attribute's values as."""

    DROPDOWN = "dropdown"
    MULTISELECT = "multiselect"
    FILE = "file"
    REFERENCE = "reference"

    CHOICES = [
        (DROPDOWN, "Dropdown"),
        (MULTISELECT, "Multi Select"),
        (FILE, "File"),
        (REFERENCE, "Reference"),
    ]
    # list of the input types that can be used in variant selection
    ALLOWED_IN_VARIANT_SELECTION = [DROPDOWN]


class AttributeType:
    ROOM_TYPE = "room-type"
    PAGE_TYPE = "page-type"

    CHOICES = [(ROOM_TYPE, "Room type"), (PAGE_TYPE, "Page type")]


class AttributeEntityType:
    """Type of a reference entity type. Must match the name of the graphql type.

    After adding new value, `REFERENCE_VALUE_NAME_MAPPING`
    and `ENTITY_TYPE_TO_MODEL_MAPPING` in vanphong/graphql/attribute/utils.py
    must be updated.
    """

    PAGE = "Page"
    ROOM = "Room"

    CHOICES = [(PAGE, "Page"), (ROOM, "Room")]
