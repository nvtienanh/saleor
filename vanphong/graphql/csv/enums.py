import graphene

from ...csv import ExportEvents, FileTypes
from ...graphql.core.enums import to_enum

ExportEventEnum = to_enum(ExportEvents)
FileTypeEnum = to_enum(FileTypes)


class ExportScope(graphene.Enum):
    ALL = "all"
    IDS = "ids"
    FILTER = "filter"

    @property
    def description(self):
        # pylint: disable=no-member
        description_mapping = {
            ExportScope.ALL.name: "Export all rooms.",
            ExportScope.IDS.name: "Export rooms with given ids.",
            ExportScope.FILTER.name: "Export the filtered rooms.",
        }
        if self.name in description_mapping:
            return description_mapping[self.name]
        raise ValueError("Unsupported enum value: %s" % self.value)


class RoomFieldEnum(graphene.Enum):
    NAME = "name"
    DESCRIPTION = "description"
    ROOM_TYPE = "room type"
    CATEGORY = "category"
    VISIBLE = "visible"
    ROOM_WEIGHT = "room weight"
    COLLECTIONS = "collections"
    CHARGE_TAXES = "charge taxes"
    ROOM_IMAGES = "room images"
    VARIANT_SKU = "variant sku"
    VARIANT_WEIGHT = "variant weight"
    VARIANT_IMAGES = "variant images"
