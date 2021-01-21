import graphene


class RoomAttributeType(graphene.Enum):
    ROOM = "ROOM"
    VARIANT = "VARIANT"


class StockAvailability(graphene.Enum):
    IN_STOCK = "AVAILABLE"
    OUT_OF_STOCK = "OUT_OF_STOCK"


class CollectionPublished(graphene.Enum):
    PUBLISHED = "published"
    HIDDEN = "hidden"


class RoomTypeConfigurable(graphene.Enum):
    CONFIGURABLE = "configurable"
    SIMPLE = "simple"


class RoomTypeEnum(graphene.Enum):
    DIGITAL = "digital"
    SHIPPABLE = "shippable"


class VariantAttributeScope(graphene.Enum):
    ALL = "all"
    VARIANT_SELECTION = "variant_selection"
    NOT_VARIANT_SELECTION = "not_variant_selection"
