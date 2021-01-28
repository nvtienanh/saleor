# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-06 10:07
from __future__ import unicode_literals

import django.db.models.deletion
import versatileimagefield.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("room", "0029_room_is_featured")]

    operations = [
        migrations.AlterModelOptions(
            name="attributechoicevalue",
            options={
                "verbose_name": "attribute choices value",
                "verbose_name_plural": "attribute choices values",
            },
        ),
        migrations.AlterModelOptions(
            name="category",
            options={"verbose_name": "category", "verbose_name_plural": "categories"},
        ),
        migrations.AlterModelOptions(
            name="room",
            options={"verbose_name": "room", "verbose_name_plural": "rooms"},
        ),
        migrations.AlterModelOptions(
            name="roomattribute",
            options={
                "ordering": ("name",),
                "verbose_name": "room attribute",
                "verbose_name_plural": "room attributes",
            },
        ),
        migrations.AlterModelOptions(
            name="roomclass",
            options={
                "verbose_name": "room class",
                "verbose_name_plural": "room classes",
            },
        ),
        migrations.AlterModelOptions(
            name="roomimage",
            options={
                "ordering": ("order",),
                "verbose_name": "room image",
                "verbose_name_plural": "room images",
            },
        ),
        migrations.AlterModelOptions(
            name="roomvariant",
            options={
                "verbose_name": "room variant",
                "verbose_name_plural": "room variants",
            },
        ),
        migrations.AlterModelOptions(
            name="variantimage",
            options={
                "verbose_name": "variant image",
                "verbose_name_plural": "variant images",
            },
        ),
        migrations.AlterField(
            model_name="room",
            name="room_class",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="rooms",
                to="room.RoomClass",
                verbose_name="room class",
            ),
        ),
        migrations.AlterField(
            model_name="roomimage",
            name="image",
            field=versatileimagefield.fields.VersatileImageField(
                upload_to="rooms", verbose_name="image"
            ),
        ),
        migrations.AlterField(
            model_name="roomimage",
            name="order",
            field=models.PositiveIntegerField(editable=False, verbose_name="order"),
        ),
        migrations.AlterField(
            model_name="roomimage",
            name="ppoi",
            field=versatileimagefield.fields.PPOIField(
                default="0.5x0.5", editable=False, max_length=20, verbose_name="ppoi"
            ),
        ),
        migrations.AlterField(
            model_name="roomimage",
            name="room",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="images",
                to="room.Room",
                verbose_name="room",
            ),
        ),
        migrations.AlterField(
            model_name="roomvariant",
            name="images",
            field=models.ManyToManyField(
                through="room.VariantImage",
                to="room.RoomImage",
                verbose_name="images",
            ),
        ),
        migrations.AlterField(
            model_name="variantimage",
            name="image",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="variant_images",
                to="room.RoomImage",
                verbose_name="image",
            ),
        ),
        migrations.AlterField(
            model_name="variantimage",
            name="variant",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="variant_images",
                to="room.RoomVariant",
                verbose_name="variant",
            ),
        ),
    ]