# Generated by Django 2.0.2 on 2018-02-28 11:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("room", "0051_auto_20180202_1106")]

    operations = [
        migrations.AlterField(
            model_name="attributechoicevalue",
            name="slug",
            field=models.SlugField(max_length=100),
        ),
        migrations.AlterField(
            model_name="category", name="slug", field=models.SlugField(max_length=128)
        ),
        migrations.AlterField(
            model_name="collection", name="slug", field=models.SlugField(max_length=128)
        ),
    ]
