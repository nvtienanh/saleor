# Generated by Django 3.1 on 2020-09-09 09:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("room", "0123_auto_20200904_1251"),
    ]

    operations = [
        migrations.AlterField(
            model_name="room",
            name="minimal_variant_price_amount",
            field=models.DecimalField(
                blank=True, decimal_places=3, max_digits=12, null=True
            ),
        ),
        migrations.AlterField(
            model_name="roomvariant",
            name="cost_price_amount",
            field=models.DecimalField(
                blank=True, decimal_places=3, max_digits=12, null=True
            ),
        ),
        migrations.AlterField(
            model_name="roomvariant",
            name="price_amount",
            field=models.DecimalField(decimal_places=3, max_digits=12),
        ),
    ]
