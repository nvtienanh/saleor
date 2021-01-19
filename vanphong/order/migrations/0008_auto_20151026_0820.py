# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("room", "0006_room_updated_at"),
        ("order", "0007_deliverygroup_tracking_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordereditem",
            name="stock",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                to="room.Stock",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="ordereditem",
            name="stock_location",
            field=models.CharField(
                default="", max_length=100, verbose_name="stock location"
            ),
        ),
    ]
