# Generated by Django 3.0.6 on 2020-07-09 11:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("room", "0118_populate_room_variant_price"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="attributeroom",
            options={"ordering": ("sort_order", "pk")},
        ),
        migrations.AlterModelOptions(
            name="attributevalue",
            options={"ordering": ("sort_order", "pk")},
        ),
        migrations.AlterModelOptions(
            name="attributevariant",
            options={"ordering": ("sort_order", "pk")},
        ),
        migrations.AlterModelOptions(
            name="room",
            options={
                "ordering": ("slug",),
                "permissions": (("manage_rooms", "Manage rooms."),),
            },
        ),
        migrations.AlterModelOptions(
            name="roomimage",
            options={"ordering": ("sort_order", "pk")},
        ),
    ]
