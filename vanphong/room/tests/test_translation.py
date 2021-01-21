import pytest

from ...attribute.models import AttributeTranslation, AttributeValueTranslation
from ..models import (
    CategoryTranslation,
    CollectionTranslation,
    RoomTranslation,
    RoomVariantTranslation,
)


@pytest.fixture
def room_translation_pl(room):
    return RoomTranslation.objects.create(
        language_code="pl",
        room=room,
        name="Polish name",
        description="Polish description",
    )


@pytest.fixture
def attribute_value_translation_fr(translated_attribute):
    value = translated_attribute.attribute.values.first()
    return AttributeValueTranslation.objects.create(
        language_code="fr", attribute_value=value, name="French name"
    )


def test_translation(room, settings, room_translation_fr):
    assert room.translated.name == "Test room"
    assert not room.translated.description

    settings.LANGUAGE_CODE = "fr"
    assert room.translated.name == "French name"
    assert room.translated.description == "French description"


def test_translation_str_returns_str_of_instance(
    room, room_translation_fr, settings
):
    assert str(room.translated) == str(room)
    settings.LANGUAGE_CODE = "fr"
    assert str(room.translated.translation) == str(room_translation_fr)


def test_wrapper_gets_proper_wrapper(
    room, room_translation_fr, settings, room_translation_pl
):
    assert room.translated.translation is None

    settings.LANGUAGE_CODE = "fr"
    assert room.translated.translation == room_translation_fr

    settings.LANGUAGE_CODE = "pl"
    assert room.translated.translation == room_translation_pl


def test_getattr(room, settings, room_translation_fr, room_type):
    settings.LANGUAGE_CODE = "fr"
    assert room.translated.room_type == room_type


def test_translation_not_override_id(settings, room, room_translation_fr):
    settings.LANGUAGE_CODE = "fr"
    translated_room = room.translated
    assert translated_room.id == room.id
    assert not translated_room.id == room_translation_fr


def test_collection_translation(settings, collection):
    settings.LANGUAGE_CODE = "fr"
    french_name = "French name"
    CollectionTranslation.objects.create(
        language_code="fr", name=french_name, collection=collection
    )
    assert collection.translated.name == french_name


def test_category_translation(settings, category):
    settings.LANGUAGE_CODE = "fr"
    french_name = "French name"
    french_description = "French description"
    CategoryTranslation.objects.create(
        language_code="fr",
        name=french_name,
        description=french_description,
        category=category,
    )
    assert category.translated.name == french_name
    assert category.translated.description == french_description


def test_room_variant_translation(settings, variant):
    settings.LANGUAGE_CODE = "fr"
    french_name = "French name"
    RoomVariantTranslation.objects.create(
        language_code="fr", name=french_name, room_variant=variant
    )
    assert variant.translated.name == french_name


def test_attribute_translation(settings, color_attribute):
    AttributeTranslation.objects.create(
        language_code="fr", attribute=color_attribute, name="French name"
    )
    assert not color_attribute.translated.name == "French name"
    settings.LANGUAGE_CODE = "fr"
    assert color_attribute.translated.name == "French name"


def test_attribute_value_translation(settings, room, attribute_value_translation_fr):
    attribute = room.room_type.room_attributes.first().values.first()
    assert not attribute.translated.name == "French name"
    settings.LANGUAGE_CODE = "fr"
    assert attribute.translated.name == "French name"


def test_voucher_translation(settings, voucher, voucher_translation_fr):
    assert not voucher.translated.name == "French name"
    settings.LANGUAGE_CODE = "fr"
    assert voucher.translated.name == "French name"
