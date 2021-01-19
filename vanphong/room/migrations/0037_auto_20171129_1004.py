# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-11-29 16:04
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("room", "0036_auto_20171115_0608")]

    operations = [
        migrations.AlterModelOptions(name="attributechoicevalue", options={}),
        migrations.AlterModelOptions(
            name="category",
            options={
                "permissions": (
                    ("view_category", "Can view categories"),
                    ("edit_category", "Can edit categories"),
                )
            },
        ),
        migrations.AlterModelOptions(
            name="room",
            options={
                "permissions": (
                    ("view_room", "Can view rooms"),
                    ("edit_room", "Can edit rooms"),
                    ("view_properties", "Can view room properties"),
                    ("edit_properties", "Can edit room properties"),
                )
            },
        ),
        migrations.AlterModelOptions(
            name="roomattribute", options={"ordering": ("slug",)}
        ),
        migrations.AlterModelOptions(name="roomclass", options={}),
        migrations.AlterModelOptions(
            name="roomimage", options={"ordering": ("order",)}
        ),
        migrations.AlterModelOptions(name="roomvariant", options={}),
        migrations.AlterModelOptions(name="variantimage", options={}),
    ]
