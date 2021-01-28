# Generated by Django 2.2.3 on 2019-07-15 07:47
from django.db import migrations
from draftjs_sanitizer import clean_draft_js
from html_to_draftjs import html_to_draftjs

from ...core.db.fields import SanitizedJSONField
from ...core.utils.draftjs import json_content_to_raw_text


def convert_rooms_html_to_json(apps, schema_editor):
    Room = apps.get_model("room", "Room")
    qs = Room.objects.all()

    for room in qs:
        description_json = room.description_json
        description_raw = json_content_to_raw_text(description_json)

        # Override the JSON description if there was nothing in it
        if not description_raw.strip():
            room.description_json = html_to_draftjs(room.description)
            room.save(update_fields=["description_json"])

    RoomTranslation = apps.get_model("room", "RoomTranslation")
    qs = RoomTranslation.objects.all()

    for translation in qs:
        description_json = translation.description_json
        description_raw = json_content_to_raw_text(description_json)

        # Override the JSON description if there was nothing in it
        if not description_raw:
            translation.description_json = html_to_draftjs(translation.description)
            translation.save(update_fields=["description_json"])


def sanitize_descriptions_json(apps, schema_editor):
    Room = apps.get_model("room", "Room")
    qs = Room.objects.all()

    for room in qs:
        room.description_json = clean_draft_js(room.description_json)
        room.save(update_fields=["description_json"])

    RoomTranslation = apps.get_model("room", "RoomTranslation")
    qs = RoomTranslation.objects.all()

    for room in qs:
        room.description_json = clean_draft_js(room.description_json)
        room.save(update_fields=["description_json"])


class Migration(migrations.Migration):

    dependencies = [("room", "0095_auto_20190618_0842")]

    operations = [
        migrations.RunPython(convert_rooms_html_to_json),
        migrations.RunPython(sanitize_descriptions_json),
        migrations.AlterField(
            model_name="room",
            name="description_json",
            field=SanitizedJSONField(
                blank=True, default=dict, sanitizer=clean_draft_js
            ),
        ),
        migrations.AlterField(
            model_name="roomtranslation",
            name="description_json",
            field=SanitizedJSONField(
                blank=True, default=dict, sanitizer=clean_draft_js
            ),
        ),
    ]