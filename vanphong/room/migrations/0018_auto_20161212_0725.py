# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-12-12 13:25
from __future__ import unicode_literals

from django.db import migrations
from django.utils.text import slugify


def create_slugs(apps, schema_editor):
    Value = apps.get_model("room", "AttributeChoiceValue")
    for value in Value.objects.all():
        value.slug = slugify(value.display)
        value.save()


class Migration(migrations.Migration):

    dependencies = [("room", "0017_attributechoicevalue_slug")]

    operations = [migrations.RunPython(create_slugs, migrations.RunPython.noop)]