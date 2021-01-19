# Generated by Django 2.2.4 on 2019-08-14 09:13
import os

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("checkout", "0020_auto_20190723_0722")]

    operations = [
        migrations.AddField(
            model_name="checkout",
            name="currency",
            field=models.CharField(
                default=os.environ.get("DEFAULT_CURRENCY", "USD"),
                max_length=settings.DEFAULT_CURRENCY_CODE_LENGTH,
            ),
        )
    ]
