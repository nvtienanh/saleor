# Generated by Django 2.2.7 on 2019-12-09 10:37

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("room", "0110_auto_20191108_0340"),
        ("hotel", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(model_name="roomvariant", name="quantity"),
        migrations.RemoveField(model_name="roomvariant", name="quantity_allocated"),
    ]
