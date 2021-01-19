# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("room", "0005_auto_20150825_1433")]

    operations = [
        migrations.AddField(
            model_name="room",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True, verbose_name="updated at", null=True
            ),
        )
    ]
