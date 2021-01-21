from __future__ import unicode_literals

from django.db import migrations


def move_data(apps, schema_editor):
    Room = apps.get_model("room", "Room")
    RoomClass = apps.get_model("room", "RoomClass")

    for room in Room.objects.all():
        attributes = room.attributes.all()
        room_class = RoomClass.objects.all()
        for attribute in attributes:
            room_class = room_class.filter(variant_attributes__in=[attribute])
        room_class = room_class.first()
        if room_class is None:
            room_class = RoomClass.objects.create(
                name="Unnamed room type", has_variants=True
            )
            room_class.variant_attributes = attributes
            room_class.save()
        room.room_class = room_class
        room.save()


class Migration(migrations.Migration):

    dependencies = [("room", "0019_auto_20161212_0230")]

    operations = [migrations.RunPython(move_data)]
