# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("room", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="room",
            name="description",
            field=models.TextField(default="", verbose_name="description", blank=True),
        )
    ]
