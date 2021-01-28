# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-02-08 14:45
from __future__ import unicode_literals

from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("room", "0010_auto_20160129_0826")]

    operations = [
        migrations.AddField(
            model_name="stock",
            name="quantity_allocated",
            field=models.IntegerField(
                default=Decimal("0"),
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="allocated quantity",
            ),
        )
    ]