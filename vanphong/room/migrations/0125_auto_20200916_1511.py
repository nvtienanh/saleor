# Generated by Django 3.1.1 on 2020-09-16 15:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("room", "0124_auto_20200909_0904"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="roomvariant",
            options={"ordering": ("sort_order", "sku")},
        ),
        migrations.AddField(
            model_name="roomvariant",
            name="sort_order",
            field=models.IntegerField(db_index=True, editable=False, null=True),
        ),
    ]
