# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-12-05 11:46
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("room", "0040_auto_20171205_0428")]

    operations = [
        migrations.RenameField(
            model_name="category", old_name="hidden", new_name="is_hidden"
        )
    ]
