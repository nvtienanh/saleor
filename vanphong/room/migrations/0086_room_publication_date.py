# Generated by Django 2.1.5 on 2019-02-05 11:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("room", "0085_auto_20190125_0025")]

    operations = [
        migrations.RenameField(
            model_name="room", old_name="available_on", new_name="publication_date"
        )
    ]
