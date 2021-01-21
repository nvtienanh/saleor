class AttributeInputType:
    """The type that we expect to render the attribute's values as."""

    DROPDOWN = "dropdown"
    MULTISELECT = "multiselect"
    FILE = "file"

    CHOICES = [(DROPDOWN, "Dropdown"), (MULTISELECT, "Multi Select"), (FILE, "File")]
    # list of the input types that can be used in variant selection
    ALLOWED_IN_VARIANT_SELECTION = [DROPDOWN]


class AttributeType:
    ROOM_TYPE = "room-type"
    PAGE_TYPE = "page-type"

    CHOICES = [(ROOM_TYPE, "Room type"), (PAGE_TYPE, "Page type")]
