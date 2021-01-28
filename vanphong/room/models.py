import datetime
from typing import TYPE_CHECKING, Iterable, Optional, Union
from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.aggregates import StringAgg
from django.db import models
from django.db.models import JSONField  # type: ignore
from django.db.models import (
    BooleanField,
    Case,
    Count,
    DateField,
    ExpressionWrapper,
    F,
    FilteredRelation,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils.encoding import smart_text
from django_measurement.models import MeasurementField
from django_prices.models import MoneyField
from measurement.measures import Weight
from mptt.managers import TreeManager
from mptt.models import MPTTModel
from versatileimagefield.fields import PPOIField, VersatileImageField

from ..account.utils import requestor_is_staff_member_or_app
from ..channel.models import Channel
from ..core.db.fields import SanitizedJSONField
from ..core.models import ModelWithMetadata, PublishableModel, SortableModel
from ..core.permissions import RoomPermissions, RoomTypePermissions
from ..core.sanitizers.editorjs_sanitizer import clean_editor_js
from ..core.utils import build_absolute_uri
from ..core.utils.draftjs import json_content_to_raw_text
from ..core.utils.translations import TranslationProxy
# from ..core.weight import WeightUnits, zero_weight
from ..discount import DiscountInfo
from ..discount.utils import calculate_discounted_price
from ..seo.models import SeoModel, SeoModelTranslation

if TYPE_CHECKING:
    # flake8: noqa
    from django.db.models import OrderBy
    from prices import Money

    from ..account.models import User
    from ..app.models import App


class Category(MPTTModel, ModelWithMetadata, SeoModel):
    name = models.CharField(max_length=250)
    slug = models.SlugField(max_length=255, unique=True, allow_unicode=True)
    description = models.TextField(blank=True)
    description_json = SanitizedJSONField(
        blank=True, default=dict, sanitizer=clean_editor_js
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    background_image = VersatileImageField(
        upload_to="category-backgrounds", blank=True, null=True
    )
    background_image_alt = models.CharField(max_length=128, blank=True)

    objects = models.Manager()
    tree = TreeManager()
    translated = TranslationProxy()

    def __str__(self) -> str:
        return self.name


class CategoryTranslation(SeoModelTranslation):
    language_code = models.CharField(max_length=10)
    category = models.ForeignKey(
        Category, related_name="translations", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    description_json = SanitizedJSONField(
        blank=True, default=dict, sanitizer=clean_editor_js
    )

    class Meta:
        unique_together = (("language_code", "category"),)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        class_ = type(self)
        return "%s(pk=%r, name=%r, category_pk=%r)" % (
            class_.__name__,
            self.pk,
            self.name,
            self.category_id,
        )


class RoomType(ModelWithMetadata):
    name = models.CharField(max_length=250)
    slug = models.SlugField(max_length=255, unique=True, allow_unicode=True)
    has_variants = models.BooleanField(default=True)
    """TODO: remove `shipping` fields
    is_shipping_required = models.BooleanField(default=True)
    """
    """TODO: remove `is_digital` fields
    is_digital = models.BooleanField(default=False)
    """
    """ TODO: Remove fields related `weight`
    weight = MeasurementField(
        measurement=Weight, unit_choices=WeightUnits.CHOICES, default=zero_weight
    )
    """

    class Meta:
        ordering = ("slug",)
        app_label = "room"
        permissions = (
            (
                RoomTypePermissions.MANAGE_ROOM_TYPES_AND_ATTRIBUTES.codename,
                "Manage room types and attributes.",
            ),
        )

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        class_ = type(self)
        return "<%s.%s(pk=%r, name=%r)>" % (
            class_.__module__,
            class_.__name__,
            self.pk,
            self.name,
        )


class RoomsQueryset(models.QuerySet):
    def published(self, channel_slug: str):
        today = datetime.date.today()
        return self.filter(
            Q(channel_listings__publication_date__lte=today)
            | Q(channel_listings__publication_date__isnull=True),
            channel_listings__channel__slug=str(channel_slug),
            channel_listings__channel__is_active=True,
            channel_listings__is_published=True,
        )

    def not_published(self, channel_slug: str):
        today = datetime.date.today()
        return self.annotate_publication_info(channel_slug).filter(
            Q(publication_date__gt=today) & Q(is_published=True)
            | Q(is_published=False)
            | Q(is_published__isnull=True)
        )

    def published_with_variants(self, channel_slug: str):
        published = self.published(channel_slug)
        query = RoomVariantChannelListing.objects.filter(
            variant_id=OuterRef("variants__id"), channel__slug=str(channel_slug)
        ).values_list("variant", flat=True)
        return published.filter(variants__in=query).distinct()

    def visible_to_user(self, requestor: Union["User", "App"], channel_slug: str):
        if requestor_is_staff_member_or_app(requestor):
            if channel_slug:
                return self.filter(channel_listings__channel__slug=str(channel_slug))
            return self.all()
        return self.published_with_variants(channel_slug)

    def annotate_publication_info(self, channel_slug: str):
        return self.annotate_is_published(channel_slug).annotate_publication_date(
            channel_slug
        )

    def annotate_is_published(self, channel_slug: str):
        query = Subquery(
            RoomChannelListing.objects.filter(
                room_id=OuterRef("pk"), channel__slug=str(channel_slug)
            ).values_list("is_published")[:1]
        )
        return self.annotate(
            is_published=ExpressionWrapper(query, output_field=BooleanField())
        )

    def annotate_publication_date(self, channel_slug: str):
        query = Subquery(
            RoomChannelListing.objects.filter(
                room_id=OuterRef("pk"), channel__slug=str(channel_slug)
            ).values_list("publication_date")[:1]
        )
        return self.annotate(
            publication_date=ExpressionWrapper(query, output_field=DateField())
        )

    def annotate_visible_in_listings(self, channel_slug):
        query = Subquery(
            RoomChannelListing.objects.filter(
                room_id=OuterRef("pk"), channel__slug=str(channel_slug)
            ).values_list("visible_in_listings")[:1]
        )
        return self.annotate(
            visible_in_listings=ExpressionWrapper(query, output_field=BooleanField())
        )

    def sort_by_attribute(
        self, attribute_pk: Union[int, str], descending: bool = False
    ):
        """Sort a query set by the values of the given room attribute.

        :param attribute_pk: The database ID (must be a numeric) of the attribute
                             to sort by.
        :param descending: The sorting direction.
        """
        from ..attribute.models import AttributeRoom, AttributeValue

        qs: models.QuerySet = self
        # If the passed attribute ID is valid, execute the sorting
        if not (isinstance(attribute_pk, int) or attribute_pk.isnumeric()):
            return qs.annotate(
                concatenated_values_order=Value(
                    None, output_field=models.IntegerField()
                ),
                concatenated_values=Value(None, output_field=models.CharField()),
            )

        # Retrieve all the rooms' attribute data IDs (assignments) and
        # room types that have the given attribute associated to them
        associated_values = tuple(
            AttributeRoom.objects.filter(attribute_id=attribute_pk).values_list(
                "pk", "room_type_id"
            )
        )

        if not associated_values:
            qs = qs.annotate(
                concatenated_values_order=Value(
                    None, output_field=models.IntegerField()
                ),
                concatenated_values=Value(None, output_field=models.CharField()),
            )

        else:
            attribute_associations, room_types_associated_to_attribute = zip(
                *associated_values
            )

            qs = qs.annotate(
                # Contains to retrieve the attribute data (singular) of each room
                # Refer to `AttributeRoom`.
                filtered_attribute=FilteredRelation(
                    relation_name="attributes",
                    condition=Q(attributes__assignment_id__in=attribute_associations),
                ),
                # Implicit `GROUP BY` required for the `StringAgg` aggregation
                grouped_ids=Count("id"),
                # String aggregation of the attribute's values to efficiently sort them
                concatenated_values=Case(
                    # If the room has no association data but has
                    # the given attribute associated to its room type,
                    # then consider the concatenated values as empty (non-null).
                    When(
                        Q(room_type_id__in=room_types_associated_to_attribute)
                        & Q(filtered_attribute=None),
                        then=models.Value(""),
                    ),
                    default=StringAgg(
                        F("filtered_attribute__values__name"),
                        delimiter=",",
                        ordering=(
                            [
                                f"filtered_attribute__values__{field_name}"
                                for field_name in AttributeValue._meta.ordering or []
                            ]
                        ),
                    ),
                    output_field=models.CharField(),
                ),
                concatenated_values_order=Case(
                    # Make the rooms having no such attribute be last in the sorting
                    When(concatenated_values=None, then=2),
                    # Put the rooms having an empty attribute value at the bottom of
                    # the other rooms.
                    When(concatenated_values="", then=1),
                    # Put the rooms having an attribute value to be always at the top
                    default=0,
                    output_field=models.IntegerField(),
                ),
            )

        # Sort by concatenated_values_order then
        # Sort each group of rooms (0, 1, 2, ...) per attribute values
        # Sort each group of rooms by name,
        # if they have the same values or not values
        ordering = "-" if descending else ""
        return qs.order_by(
            f"{ordering}concatenated_values_order",
            f"{ordering}concatenated_values",
            f"{ordering}name",
        )


class Room(SeoModel, ModelWithMetadata):
    room_type = models.ForeignKey(
        RoomType, related_name="rooms", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=250)
    slug = models.SlugField(max_length=255, unique=True, allow_unicode=True)
    description = models.TextField(blank=True)
    description_json = SanitizedJSONField(
        blank=True, default=dict, sanitizer=clean_editor_js
    )
    category = models.ForeignKey(
        Category,
        related_name="rooms",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True, null=True)
    charge_taxes = models.BooleanField(default=True)
    """ TODO: Remove fields related `weight`
    weight = MeasurementField(
        measurement=Weight, unit_choices=WeightUnits.CHOICES, blank=True, null=True
    )
    """
    default_variant = models.OneToOneField(
        "RoomVariant",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    rating = models.FloatField(null=True, blank=True)

    objects = RoomsQueryset.as_manager()
    translated = TranslationProxy()

    class Meta:
        app_label = "room"
        ordering = ("slug",)
        permissions = (
            (RoomPermissions.MANAGE_ROOMS.codename, "Manage rooms."),
        )

    def __iter__(self):
        if not hasattr(self, "__variants"):
            setattr(self, "__variants", self.variants.all())
        return iter(getattr(self, "__variants"))

    def __repr__(self) -> str:
        class_ = type(self)
        return "<%s.%s(pk=%r, name=%r)>" % (
            class_.__module__,
            class_.__name__,
            self.pk,
            self.name,
        )

    def __str__(self) -> str:
        return self.name

    @property
    def plain_text_description(self) -> str:
        return json_content_to_raw_text(self.description_json)

    def get_first_image(self):
        images = list(self.images.all())
        return images[0] if images else None

    @staticmethod
    def sort_by_attribute_fields() -> list:
        return ["concatenated_values_order", "concatenated_values", "name"]


class RoomTranslation(SeoModelTranslation):
    language_code = models.CharField(max_length=10)
    room = models.ForeignKey(
        Room, related_name="translations", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    description_json = SanitizedJSONField(
        blank=True, default=dict, sanitizer=clean_editor_js
    )

    class Meta:
        unique_together = (("language_code", "room"),)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        class_ = type(self)
        return "%s(pk=%r, name=%r, room_pk=%r)" % (
            class_.__name__,
            self.pk,
            self.name,
            self.room_id,
        )


class RoomVariantQueryset(models.QuerySet):
    def annotate_quantities(self):
        return self.annotate(
            quantity=Coalesce(Sum("stocks__quantity"), 0),
            quantity_allocated=Coalesce(
                Sum("stocks__allocations__quantity_allocated"), 0
            ),
        )


class RoomChannelListing(PublishableModel):
    room = models.ForeignKey(
        Room,
        null=False,
        blank=False,
        related_name="channel_listings",
        on_delete=models.CASCADE,
    )
    channel = models.ForeignKey(
        Channel,
        null=False,
        blank=False,
        related_name="room_listings",
        on_delete=models.CASCADE,
    )
    visible_in_listings = models.BooleanField(default=False)
    available_for_purchase = models.DateField(blank=True, null=True)
    currency = models.CharField(max_length=settings.DEFAULT_CURRENCY_CODE_LENGTH)
    discounted_price_amount = models.DecimalField(
        max_digits=settings.DEFAULT_MAX_DIGITS,
        decimal_places=settings.DEFAULT_DECIMAL_PLACES,
        blank=True,
        null=True,
    )
    discounted_price = MoneyField(
        amount_field="discounted_price_amount", currency_field="currency"
    )

    class Meta:
        unique_together = [["room", "channel"]]
        ordering = ("pk",)

    def is_available_for_purchase(self):
        return (
            self.available_for_purchase is not None
            and datetime.date.today() >= self.available_for_purchase
        )


class RoomVariant(SortableModel, ModelWithMetadata):
    sku = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255, blank=True)
    room = models.ForeignKey(
        Room, related_name="variants", on_delete=models.CASCADE
    )
    images = models.ManyToManyField("RoomImage", through="VariantImage")
    track_inventory = models.BooleanField(default=True)

    """ TODO: Remove fields related `weight`
    weight = MeasurementField(
        measurement=Weight, unit_choices=WeightUnits.CHOICES, blank=True, null=True
    )
    """

    objects = RoomVariantQueryset.as_manager()
    translated = TranslationProxy()

    class Meta:
        ordering = ("sort_order", "sku")
        app_label = "room"

    def __str__(self) -> str:
        return self.name or self.sku

    def get_price(
        self,
        room: Room,
        collections: Iterable["Collection"],
        channel: Channel,
        channel_listing: "RoomVariantChannelListing",
        discounts: Optional[Iterable[DiscountInfo]] = None,
    ) -> "Money":
        return calculate_discounted_price(
            room=room,
            price=channel_listing.price,
            discounts=discounts,
            collections=collections,
            channel=channel,
        )

    """ TODO: Remove fields related `weight`
    def get_weight(self):
        return self.weight or self.room.weight or self.room.room_type.weight
    """

    """ TODO: Remove fields related `shipping`
    def is_shipping_required(self) -> bool:
        return self.room.room_type.is_shipping_required
    """

    def is_digital(self) -> bool:
        is_digital = self.room.room_type.is_digital
        return not self.is_shipping_required() and is_digital

    def display_room(self, translated: bool = False) -> str:
        if translated:
            room = self.room.translated
            variant_display = str(self.translated)
        else:
            variant_display = str(self)
            room = self.room
        room_display = (
            f"{room} ({variant_display})" if variant_display else str(room)
        )
        return smart_text(room_display)

    def get_first_image(self) -> "RoomImage":
        images = list(self.images.all())
        return images[0] if images else self.room.get_first_image()

    def get_ordering_queryset(self):
        return self.room.variants.all()


class RoomVariantTranslation(models.Model):
    language_code = models.CharField(max_length=10)
    room_variant = models.ForeignKey(
        RoomVariant, related_name="translations", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255, blank=True)

    translated = TranslationProxy()

    class Meta:
        unique_together = (("language_code", "room_variant"),)

    def __repr__(self):
        class_ = type(self)
        return "%s(pk=%r, name=%r, variant_pk=%r)" % (
            class_.__name__,
            self.pk,
            self.name,
            self.room_variant_id,
        )

    def __str__(self):
        return self.name or str(self.room_variant)


class RoomVariantChannelListing(models.Model):
    variant = models.ForeignKey(
        RoomVariant,
        null=False,
        blank=False,
        related_name="channel_listings",
        on_delete=models.CASCADE,
    )
    channel = models.ForeignKey(
        Channel,
        null=False,
        blank=False,
        related_name="variant_listings",
        on_delete=models.CASCADE,
    )
    currency = models.CharField(max_length=settings.DEFAULT_CURRENCY_CODE_LENGTH)
    price_amount = models.DecimalField(
        max_digits=settings.DEFAULT_MAX_DIGITS,
        decimal_places=settings.DEFAULT_DECIMAL_PLACES,
    )
    price = MoneyField(amount_field="price_amount", currency_field="currency")

    cost_price_amount = models.DecimalField(
        max_digits=settings.DEFAULT_MAX_DIGITS,
        decimal_places=settings.DEFAULT_DECIMAL_PLACES,
        blank=True,
        null=True,
    )
    cost_price = MoneyField(amount_field="cost_price_amount", currency_field="currency")

    class Meta:
        unique_together = [["variant", "channel"]]
        ordering = ("pk",)


class DigitalContent(ModelWithMetadata):
    FILE = "file"
    TYPE_CHOICES = ((FILE, "digital_room"),)
    use_default_settings = models.BooleanField(default=True)
    automatic_fulfillment = models.BooleanField(default=False)
    content_type = models.CharField(max_length=128, default=FILE, choices=TYPE_CHOICES)
    room_variant = models.OneToOneField(
        RoomVariant, related_name="digital_content", on_delete=models.CASCADE
    )
    content_file = models.FileField(upload_to="digital_contents", blank=True)
    max_downloads = models.IntegerField(blank=True, null=True)
    url_valid_days = models.IntegerField(blank=True, null=True)

    def create_new_url(self) -> "DigitalContentUrl":
        return self.urls.create()


class DigitalContentUrl(models.Model):
    token = models.UUIDField(editable=False, unique=True)
    content = models.ForeignKey(
        DigitalContent, related_name="urls", on_delete=models.CASCADE
    )
    created = models.DateTimeField(auto_now_add=True)
    download_num = models.IntegerField(default=0)
    line = models.OneToOneField(
        "order.OrderLine",
        related_name="digital_content_url",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if not self.token:
            self.token = str(uuid4()).replace("-", "")
        super().save(force_insert, force_update, using, update_fields)

    def get_absolute_url(self) -> Optional[str]:
        url = reverse("digital-room", kwargs={"token": str(self.token)})
        return build_absolute_uri(url)


class RoomImage(SortableModel):
    room = models.ForeignKey(
        Room, related_name="images", on_delete=models.CASCADE
    )
    image = VersatileImageField(upload_to="rooms", ppoi_field="ppoi", blank=False)
    ppoi = PPOIField()
    alt = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ("sort_order", "pk")
        app_label = "room"

    def get_ordering_queryset(self):
        return self.room.images.all()


class VariantImage(models.Model):
    variant = models.ForeignKey(
        "RoomVariant", related_name="variant_images", on_delete=models.CASCADE
    )
    image = models.ForeignKey(
        RoomImage, related_name="variant_images", on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("variant", "image")


class CollectionRoom(SortableModel):
    collection = models.ForeignKey(
        "Collection", related_name="collectionroom", on_delete=models.CASCADE
    )
    room = models.ForeignKey(
        Room, related_name="collectionroom", on_delete=models.CASCADE
    )

    class Meta:
        unique_together = (("collection", "room"),)

    def get_ordering_queryset(self):
        return self.room.collectionroom.all()


class CollectionsQueryset(models.QuerySet):
    def published(self, channel_slug: str):
        today = datetime.date.today()
        return self.filter(
            Q(channel_listings__publication_date__lte=today)
            | Q(channel_listings__publication_date__isnull=True),
            channel_listings__channel__slug=str(channel_slug),
            channel_listings__channel__is_active=True,
            channel_listings__is_published=True,
        )

    def visible_to_user(self, requestor: Union["User", "App"], channel_slug: str):
        if requestor_is_staff_member_or_app(requestor):
            if channel_slug:
                return self.filter(channel_listings__channel__slug=str(channel_slug))
            return self.all()
        return self.published(channel_slug)


class Collection(SeoModel, ModelWithMetadata):
    name = models.CharField(max_length=250, unique=True)
    slug = models.SlugField(max_length=255, unique=True, allow_unicode=True)
    rooms = models.ManyToManyField(
        Room,
        blank=True,
        related_name="collections",
        through=CollectionRoom,
        through_fields=("collection", "room"),
    )
    background_image = VersatileImageField(
        upload_to="collection-backgrounds", blank=True, null=True
    )
    background_image_alt = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    description_json = SanitizedJSONField(
        blank=True, default=dict, sanitizer=clean_editor_js
    )

    objects = CollectionsQueryset.as_manager()

    translated = TranslationProxy()

    class Meta:
        ordering = ("slug",)

    def __str__(self) -> str:
        return self.name


class CollectionChannelListing(PublishableModel):
    collection = models.ForeignKey(
        Collection,
        null=False,
        blank=False,
        related_name="channel_listings",
        on_delete=models.CASCADE,
    )
    channel = models.ForeignKey(
        Channel,
        null=False,
        blank=False,
        related_name="collection_listings",
        on_delete=models.CASCADE,
    )

    class Meta:
        unique_together = [["collection", "channel"]]
        ordering = ("pk",)


class CollectionTranslation(SeoModelTranslation):
    language_code = models.CharField(max_length=10)
    collection = models.ForeignKey(
        Collection, related_name="translations", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    description_json = SanitizedJSONField(
        blank=True, default=dict, sanitizer=clean_editor_js
    )

    class Meta:
        unique_together = (("language_code", "collection"),)

    def __repr__(self):
        class_ = type(self)
        return "%s(pk=%r, name=%r, collection_pk=%r)" % (
            class_.__name__,
            self.pk,
            self.name,
            self.collection_id,
        )

    def __str__(self) -> str:
        return self.name
