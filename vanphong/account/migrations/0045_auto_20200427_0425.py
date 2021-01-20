# Generated by Django 3.0.5 on 2020-04-27 09:25
from copy import deepcopy

from django.db import migrations

from vanphong.plugins.manager import get_plugins_manager


def create_payments_customer_ids():
    plugins = get_plugins_manager().plugins

    return {
        f"{plugin.PLUGIN_NAME.strip().upper()}.customer_id": (
            f"{plugin.PLUGIN_ID.strip().upper()}.customer_id"
        )
        for plugin in plugins
    }


def convert_user_payments_customer_id(apps, schema_editor):
    users = (
        apps.get_model("account", "User")
        .objects.exclude(private_metadata={})
        .iterator()
    )
    payments_customer_ids = create_payments_customer_ids()

    for user in users:
        private_metadata = deepcopy(user.private_metadata)

        for key, value in private_metadata.items():
            if key in payments_customer_ids:
                user.private_metadata[payments_customer_ids[key]] = value
                del user.private_metadata[key]
                user.save()


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0044_unmount_app_and_app_token"),
        ("plugins", "0002_auto_20200417_0335"),
    ]

    operations = [migrations.RunPython(convert_user_payments_customer_id)]
