# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from decimal import Decimal

import django.core.validators
import versatileimagefield.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AttributeChoiceValue",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                (
                    "display",
                    models.CharField(max_length=100, verbose_name="display name"),
                ),
                (
                    "color",
                    models.CharField(
                        blank=True,
                        max_length=7,
                        verbose_name="color",
                        validators=[
                            django.core.validators.RegexValidator(
                                "^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$"
                            )
                        ],
                    ),
                ),
                (
                    "image",
                    versatileimagefield.fields.VersatileImageField(
                        upload_to="attributes",
                        null=True,
                        verbose_name="image",
                        blank=True,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Category",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("name", models.CharField(max_length=128, verbose_name="name")),
                ("slug", models.SlugField(verbose_name="slug")),
                (
                    "description",
                    models.TextField(verbose_name="description", blank=True),
                ),
                ("hidden", models.BooleanField(default=False, verbose_name="hidden")),
                ("lft", models.PositiveIntegerField(editable=False, db_index=True)),
                ("rght", models.PositiveIntegerField(editable=False, db_index=True)),
                ("tree_id", models.PositiveIntegerField(editable=False, db_index=True)),
                ("level", models.PositiveIntegerField(editable=False, db_index=True)),
                (
                    "parent",
                    models.ForeignKey(
                        related_name="children",
                        verbose_name="parent",
                        blank=True,
                        to="room.Category",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                    ),
                ),
            ],
            options={"verbose_name_plural": "categories"},
        ),
        migrations.CreateModel(
            name="FixedRoomDiscount",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                (
                    "discount",
                    models.DecimalField(
                        verbose_name="discount value", max_digits=12, decimal_places=2
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Room",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("name", models.CharField(max_length=128, verbose_name="name")),
                ("description", models.TextField(verbose_name="description")),
                (
                    "price",
                    models.DecimalField(
                        verbose_name="price", max_digits=12, decimal_places=2
                    ),
                ),
                (
                    "weight",
                    models.DecimalField(
                        verbose_name="weight", max_digits=6, decimal_places=2
                    ),
                ),
                (
                    "available_on",
                    models.DateField(
                        null=True, verbose_name="available on", blank=True
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RoomAttribute",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("name", models.SlugField(unique=True, verbose_name="internal name")),
                (
                    "display",
                    models.CharField(max_length=100, verbose_name="display name"),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="RoomImage",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                (
                    "image",
                    versatileimagefield.fields.VersatileImageField(
                        upload_to="rooms"
                    ),
                ),
                (
                    "ppoi",
                    versatileimagefield.fields.PPOIField(
                        default="0.5x0.5", max_length=20, editable=False
                    ),
                ),
                (
                    "alt",
                    models.CharField(
                        max_length=128, verbose_name="short description", blank=True
                    ),
                ),
                ("order", models.PositiveIntegerField(editable=False)),
                (
                    "room",
                    models.ForeignKey(
                        related_name="images",
                        to="room.Room",
                        on_delete=django.db.models.deletion.CASCADE,
                    ),
                ),
            ],
            options={"ordering": ["order"]},
        ),
        migrations.CreateModel(
            name="RoomVariant",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                (
                    "sku",
                    models.CharField(unique=True, max_length=32, verbose_name="SKU"),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=100, verbose_name="variant name", blank=True
                    ),
                ),
                (
                    "price_override",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        blank=True,
                        null=True,
                        verbose_name="price override",
                    ),
                ),
                (
                    "weight_override",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=6,
                        blank=True,
                        null=True,
                        verbose_name="weight override",
                    ),
                ),
                (
                    "attributes",
                    models.TextField(default="{}", verbose_name="attributes"),
                ),
                (
                    "room",
                    models.ForeignKey(
                        related_name="variants",
                        to="room.Room",
                        on_delete=django.db.models.deletion.CASCADE,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Stock",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("location", models.CharField(max_length=100, verbose_name="location")),
                (
                    "quantity",
                    models.IntegerField(
                        default=Decimal("1"),
                        verbose_name="quantity",
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "cost_price",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        blank=True,
                        null=True,
                        verbose_name="cost price",
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        related_name="stock",
                        verbose_name="variant",
                        to="room.RoomVariant",
                        on_delete=django.db.models.deletion.CASCADE,
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="room",
            name="attributes",
            field=models.ManyToManyField(
                related_name="rooms",
                null=True,
                to="room.RoomAttribute",
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="room",
            name="categories",
            field=models.ManyToManyField(
                related_name="rooms",
                verbose_name="categories",
                to="room.Category",
            ),
        ),
        migrations.AddField(
            model_name="fixedroomdiscount",
            name="rooms",
            field=models.ManyToManyField(to="room.Room", blank=True),
        ),
        migrations.AddField(
            model_name="attributechoicevalue",
            name="attribute",
            field=models.ForeignKey(
                related_name="values",
                to="room.RoomAttribute",
                on_delete=django.db.models.deletion.CASCADE,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="stock", unique_together=set([("variant", "location")])
        ),
    ]
