# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-01-29 14:26
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("room", "0009_discount_categories")]

    operations = [
        migrations.RemoveField(model_name="discount", name="categories"),
        migrations.RemoveField(model_name="discount", name="rooms"),
        migrations.DeleteModel(name="Discount"),
    ]
