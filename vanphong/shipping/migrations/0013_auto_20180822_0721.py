# Generated by Django 2.0.3 on 2018-08-22 12:20

import django.db.models.deletion
import django_countries.fields
import django_measurement.models
from django.db import migrations, models

import vanphong.core.weight


class Migration(migrations.Migration):

    dependencies = [
        ("checkout", "0010_auto_20180822_0720"),
        ("order", "0052_auto_20180822_0720"),
        ("shipping", "0012_remove_legacy_shipping_methods"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShippingMethodTranslation",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("language_code", models.CharField(max_length=10)),
                ("name", models.CharField(blank=True, max_length=255, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="ShippingZone",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                (
                    "countries",
                    django_countries.fields.CountryField(max_length=749, multiple=True),
                ),
            ],
            options={"permissions": (("manage_shipping", "Manage shipping."),)},
        ),
        migrations.AlterUniqueTogether(
            name="shippingmethodcountry", unique_together=set()
        ),
        migrations.RemoveField(
            model_name="shippingmethodcountry", name="shipping_method"
        ),
        migrations.AlterModelOptions(name="shippingmethod", options={}),
        migrations.RemoveField(model_name="shippingmethod", name="description"),
        migrations.AddField(
            model_name="shippingmethod",
            name="maximum_order_price",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=12, null=True
            ),
        ),
        migrations.AddField(
            model_name="shippingmethod",
            name="maximum_order_weight",
            field=django_measurement.models.MeasurementField(
                blank=True, measurement_class="Mass", null=True
            ),
        ),
        migrations.AddField(
            model_name="shippingmethod",
            name="minimum_order_price",
            field=models.DecimalField(
                blank=True, decimal_places=2, default=0, max_digits=12, null=True
            ),
        ),
        migrations.AddField(
            model_name="shippingmethod",
            name="minimum_order_weight",
            field=django_measurement.models.MeasurementField(
                blank=True,
                default=vanphong.core.weight.zero_weight,
                measurement_class="Mass",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="shippingmethod",
            name="price",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="shippingmethod",
            name="type",
            field=models.CharField(
                choices=[
                    ("price", "Price based shipping"),
                    ("weight", "Weight based shipping"),
                ],
                default=None,
                max_length=30,
            ),
            preserve_default=False,
        ),
        migrations.DeleteModel(name="ShippingMethodCountry"),
        migrations.AddField(
            model_name="shippingmethodtranslation",
            name="shipping_method",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="translations",
                to="shipping.ShippingMethod",
            ),
        ),
        migrations.AddField(
            model_name="shippingmethod",
            name="shipping_zone",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="shipping_methods",
                to="shipping.ShippingZone",
            ),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name="shippingmethodtranslation",
            unique_together={("language_code", "shipping_method")},
        ),
    ]
