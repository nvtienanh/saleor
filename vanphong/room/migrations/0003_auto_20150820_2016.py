# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("room", "0002_auto_20150722_0545")]

    operations = [
        migrations.AlterField(
            model_name="room",
            name="attributes",
            field=models.ManyToManyField(
                related_name="rooms", to="room.RoomAttribute", blank=True
            ),
        )
    ]
