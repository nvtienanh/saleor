# Generated by Django 3.1.5 on 2021-01-28 05:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hotel', '0012_auto_20210115_1307'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='hotel',
            name='shipping_zones',
        ),
    ]