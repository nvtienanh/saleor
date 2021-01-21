from __future__ import unicode_literals

import json

from django.db import migrations


def move_data(apps, schema_editor):
    RoomVariant = apps.get_model("room", "RoomVariant")

    for variant in RoomVariant.objects.all():
        variant.attributes_postgres = json.loads(variant.attributes)
        variant.save()


class Migration(migrations.Migration):

    dependencies = [("room", "0023_auto_20161211_1912")]

    operations = [
        migrations.RunPython(move_data),
        migrations.RemoveField(model_name="roomvariant", name="attributes"),
        migrations.RenameField(
            model_name="roomvariant",
            old_name="attributes_postgres",
            new_name="attributes",
        ),
    ]
