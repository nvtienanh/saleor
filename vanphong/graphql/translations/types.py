import graphene
from django.conf import settings

from ...attribute import models as attribute_models
from ...core.permissions import DiscountPermissions, ShippingPermissions
from ...discount import models as discount_models
from ...menu import models as menu_models
from ...page import models as page_models
from ...room import models as room_models
from ...shipping import models as shipping_models
from ...site import models as site_models
from ..channel import ChannelContext
from ..core.connection import CountableDjangoObjectType
from ..core.types import LanguageDisplay
from ..core.utils import str_to_enum
from ..decorators import permission_required
from .enums import LanguageCodeEnum
from .fields import TranslationField

BASIC_TRANSLATABLE_FIELDS = ["id", "name"]
EXTENDED_TRANSLATABLE_FIELDS = [
    "id",
    "name",
    "description",
    "description_json",
    "seo_title",
    "seo_description",
]


class BaseTranslationType(CountableDjangoObjectType):
    language = graphene.Field(
        LanguageDisplay, description="Translation language.", required=True
    )

    class Meta:
        abstract = True

    @staticmethod
    def resolve_language(root, *_args):
        try:
            language = next(
                language[1]
                for language in settings.LANGUAGES
                if language[0] == root.language_code
            )
        except StopIteration:
            return None
        return LanguageDisplay(
            code=LanguageCodeEnum[str_to_enum(root.language_code)], language=language
        )


class AttributeValueTranslation(BaseTranslationType):
    class Meta:
        model = attribute_models.AttributeValueTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class AttributeValueTranslatableContent(CountableDjangoObjectType):
    translation = TranslationField(
        AttributeValueTranslation, type_name="attribute value"
    )
    attribute_value = graphene.Field(
        "vanphong.graphql.attribute.types.AttributeValue",
        description="Represents a value of an attribute.",
    )

    class Meta:
        model = attribute_models.AttributeValue
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    @staticmethod
    def resolve_attribute_value(root: attribute_models.AttributeValue, _info):
        return root


class AttributeTranslation(BaseTranslationType):
    class Meta:
        model = attribute_models.AttributeTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class AttributeTranslatableContent(CountableDjangoObjectType):
    translation = TranslationField(AttributeTranslation, type_name="attribute")
    attribute = graphene.Field(
        "vanphong.graphql.attribute.types.Attribute",
        description="Custom attribute of a room.",
    )

    class Meta:
        model = attribute_models.Attribute
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    @staticmethod
    def resolve_attribute(root: attribute_models.Attribute, _info):
        return root


class RoomVariantTranslation(BaseTranslationType):
    class Meta:
        model = room_models.RoomVariantTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class RoomVariantTranslatableContent(CountableDjangoObjectType):
    translation = TranslationField(
        RoomVariantTranslation, type_name="room variant"
    )
    room_variant = graphene.Field(
        "vanphong.graphql.room.types.rooms.RoomVariant",
        description=(
            "Represents a version of a room such as different size or color."
        ),
    )

    class Meta:
        model = room_models.RoomVariant
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    @staticmethod
    def resolve_room_variant(root: room_models.RoomVariant, info):
        return ChannelContext(node=root, channel_slug=None)


class RoomTranslation(BaseTranslationType):
    class Meta:
        model = room_models.RoomTranslation
        interfaces = [graphene.relay.Node]
        only_fields = EXTENDED_TRANSLATABLE_FIELDS


class RoomTranslatableContent(CountableDjangoObjectType):
    translation = TranslationField(RoomTranslation, type_name="room")
    room = graphene.Field(
        "vanphong.graphql.room.types.rooms.Room",
        description="Represents an individual item for sale in the storefront.",
    )

    class Meta:
        model = room_models.Room
        interfaces = [graphene.relay.Node]
        only_fields = EXTENDED_TRANSLATABLE_FIELDS

    @staticmethod
    def resolve_room(root: room_models.Room, info):
        return ChannelContext(node=root, channel_slug=None)


class CollectionTranslation(BaseTranslationType):
    class Meta:
        model = room_models.CollectionTranslation
        interfaces = [graphene.relay.Node]
        only_fields = EXTENDED_TRANSLATABLE_FIELDS


class CollectionTranslatableContent(CountableDjangoObjectType):
    translation = TranslationField(CollectionTranslation, type_name="collection")
    collection = graphene.Field(
        "vanphong.graphql.room.types.rooms.Collection",
        description="Represents a collection of rooms.",
    )

    class Meta:
        model = room_models.Collection
        interfaces = [graphene.relay.Node]
        only_fields = EXTENDED_TRANSLATABLE_FIELDS

    @staticmethod
    def resolve_collection(root: room_models.Collection, info):
        collection = room_models.Collection.objects.all().filter(pk=root.id).first()
        return (
            ChannelContext(node=collection, channel_slug=None) if collection else None
        )


class CategoryTranslation(BaseTranslationType):
    class Meta:
        model = room_models.CategoryTranslation
        interfaces = [graphene.relay.Node]
        only_fields = EXTENDED_TRANSLATABLE_FIELDS


class CategoryTranslatableContent(CountableDjangoObjectType):
    translation = TranslationField(CategoryTranslation, type_name="category")
    category = graphene.Field(
        "vanphong.graphql.room.types.rooms.Category",
        description="Represents a single category of rooms.",
    )

    class Meta:
        model = room_models.Category
        interfaces = [graphene.relay.Node]
        only_fields = EXTENDED_TRANSLATABLE_FIELDS

    @staticmethod
    def resolve_category(root: room_models.Category, _info):
        return root


class PageTranslation(BaseTranslationType):
    class Meta:
        model = page_models.PageTranslation
        interfaces = [graphene.relay.Node]
        only_fields = [
            "content",
            "content_json",
            "id",
            "seo_description",
            "seo_title",
            "title",
        ]


class PageTranslatableContent(CountableDjangoObjectType):
    translation = TranslationField(PageTranslation, type_name="page")
    page = graphene.Field(
        "vanphong.graphql.page.types.Page",
        description=(
            "A static page that can be manually added by a shop operator ",
            "through the dashboard.",
        ),
    )

    class Meta:
        model = page_models.Page
        interfaces = [graphene.relay.Node]
        only_fields = [
            "content",
            "content_json",
            "id",
            "seo_description",
            "seo_title",
            "title",
        ]

    @staticmethod
    def resolve_page(root: page_models.Page, info):
        return (
            page_models.Page.objects.visible_to_user(info.context.user)
            .filter(pk=root.id)
            .first()
        )


class VoucherTranslation(BaseTranslationType):
    class Meta:
        model = discount_models.VoucherTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class VoucherTranslatableContent(CountableDjangoObjectType):
    translation = TranslationField(VoucherTranslation, type_name="voucher")
    voucher = graphene.Field(
        "vanphong.graphql.discount.types.Voucher",
        description=(
            "Vouchers allow giving discounts to particular customers on categories, "
            "collections or specific rooms. They can be used during checkout by "
            "providing valid voucher codes."
        ),
    )

    class Meta:
        model = discount_models.Voucher
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    @staticmethod
    @permission_required(DiscountPermissions.MANAGE_DISCOUNTS)
    def resolve_voucher(root: discount_models.Voucher, _info):
        return ChannelContext(node=root, channel_slug=None)


class SaleTranslation(BaseTranslationType):
    class Meta:
        model = discount_models.SaleTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class SaleTranslatableContent(CountableDjangoObjectType):
    translation = TranslationField(SaleTranslation, type_name="sale")
    sale = graphene.Field(
        "vanphong.graphql.discount.types.Sale",
        description=(
            "Sales allow creating discounts for categories, collections "
            "or rooms and are visible to all the customers."
        ),
    )

    class Meta:
        model = discount_models.Sale
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    @staticmethod
    @permission_required(DiscountPermissions.MANAGE_DISCOUNTS)
    def resolve_sale(root: discount_models.Sale, _info):
        return ChannelContext(node=root, channel_slug=None)


class ShopTranslation(BaseTranslationType):
    class Meta:
        model = site_models.SiteSettingsTranslation
        interfaces = [graphene.relay.Node]
        only_fields = ["description", "header_text", "id"]


class MenuItemTranslation(BaseTranslationType):
    class Meta:
        model = menu_models.MenuItemTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class MenuItemTranslatableContent(CountableDjangoObjectType):
    translation = TranslationField(MenuItemTranslation, type_name="menu item")
    menu_item = graphene.Field(
        "vanphong.graphql.menu.types.MenuItem",
        description=(
            "Represents a single item of the related menu. Can store categories, "
            "collection or pages."
        ),
    )

    class Meta:
        model = menu_models.MenuItem
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    @staticmethod
    def resolve_menu_item(root: menu_models.MenuItem, _info):
        return ChannelContext(node=root, channel_slug=None)


class ShippingMethodTranslation(BaseTranslationType):
    class Meta:
        model = shipping_models.ShippingMethodTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class ShippingMethodTranslatableContent(CountableDjangoObjectType):
    translation = TranslationField(
        ShippingMethodTranslation, type_name="shipping method"
    )
    shipping_method = graphene.Field(
        "vanphong.graphql.shipping.types.ShippingMethod",
        description=(
            "Shipping method are the methods you'll use to get customer's orders "
            " to them. They are directly exposed to the customers."
        ),
    )

    class Meta:
        model = shipping_models.ShippingMethod
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    @staticmethod
    @permission_required(ShippingPermissions.MANAGE_SHIPPING)
    def resolve_shipping_method(root: shipping_models.ShippingMethod, _info):
        return ChannelContext(node=root, channel_slug=None)