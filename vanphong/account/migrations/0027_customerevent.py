# Generated by Django 2.2.1 on 2019-05-09 10:37

import django.contrib.postgres.fields.jsonb
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import vanphong.core.utils.json_serializer


class Migration(migrations.Migration):

    dependencies = [
        ("order", "0070_drop_update_event_and_rename_events"),
        ("account", "0026_user_avatar"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerEvent",
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
                (
                    "date",
                    models.DateTimeField(
                        default=django.utils.timezone.now, editable=False
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("ACCOUNT_CREATED", "account_created"),
                            ("PASSWORD_RESET_LINK_SENT", "password_reset_link_sent"),
                            ("PASSWORD_RESET", "password_reset"),
                            ("PLACED_ORDER", "placed_order"),
                            ("NOTE_ADDED_TO_ORDER", "note_added_to_order"),
                            ("DIGITAL_LINK_DOWNLOADED", "digital_link_downloaded"),
                            ("CUSTOMER_DELETED", "customer_deleted"),
                            ("NAME_ASSIGNED", "name_assigned"),
                            ("EMAIL_ASSIGNED", "email_assigned"),
                            ("NOTE_ADDED", "note_added"),
                        ],
                        max_length=255,
                    ),
                ),
                (
                    "parameters",
                    django.contrib.postgres.fields.jsonb.JSONField(
                        blank=True,
                        default=dict,
                        encoder=vanphong.core.utils.json_serializer.CustomJsonEncoder,
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="order.Order",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("date",)},
        )
    ]