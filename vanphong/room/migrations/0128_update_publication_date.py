from datetime import date

from django.db import migrations


def set_missing_room_publication_date(apps, schema_editor):
    Room = apps.get_model("room", "Room")
    published_room = Room.objects.filter(
        publication_date__isnull=True, is_published=True
    )
    published_room.update(publication_date=date.today())


def set_missing_collection_publication_date(apps, schema_editor):
    Collection = apps.get_model("room", "Collection")
    published_collection = Collection.objects.filter(
        publication_date__isnull=True, is_published=True
    )
    published_collection.update(publication_date=date.today())


class Migration(migrations.Migration):
    dependencies = [
        ("room", "0127_auto_20201001_0933"),
    ]

    operations = [
        migrations.RunPython(set_missing_room_publication_date),
        migrations.RunPython(set_missing_collection_publication_date),
    ]
