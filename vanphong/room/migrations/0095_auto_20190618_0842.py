from django.db import migrations


def move_tax_rate_to_meta(apps, schema_editor):
    RoomType = apps.get_model("room", "RoomType")
    Room = apps.get_model("room", "Room")
    room_types = RoomType.objects.filter(tax_rate__isnull=False).exclude(
        tax_rate=""
    )
    rooms = Room.objects.filter(tax_rate__isnull=False).exclude(tax_rate="")
    room_types_list = []
    for room_type in room_types:
        if "taxes" not in room_type.meta:
            room_type.meta["taxes"] = {}
        room_type.meta["taxes"]["vatlayer"] = {
            "code": room_type.tax_rate,
            "description": room_type.tax_rate,
        }
        room_types_list.append(room_type)
    RoomType.objects.bulk_update(room_types_list, ["meta"])

    room_list = []
    for room in rooms:
        if "taxes" not in room.meta:
            room.meta["taxes"] = {}
        room.meta["taxes"]["vatlayer"] = {
            "code": room.tax_rate,
            "description": room.tax_rate,
        }
        room_list.append(room)
    Room.objects.bulk_update(room_list, ["meta"])


class Migration(migrations.Migration):

    dependencies = [("room", "0094_auto_20190618_0430")]

    operations = [
        migrations.RunPython(move_tax_rate_to_meta),
        migrations.RemoveField(model_name="room", name="tax_rate"),
        migrations.RemoveField(model_name="roomtype", name="tax_rate"),
    ]
