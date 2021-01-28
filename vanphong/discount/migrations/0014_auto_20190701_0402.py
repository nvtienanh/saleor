# Generated by Django 2.2.2 on 2019-07-01 09:02

from django.db import migrations, models

from vanphong.discount import VoucherType


def replace_value_vocucher_type(apps, schema_editor):
    cls = apps.get_model("discount", "Voucher")
    cls.objects.filter(type="value").update(type=VoucherType.ENTIRE_ORDER)


class Migration(migrations.Migration):

    dependencies = [("discount", "0013_auto_20190618_0733")]

    operations = [
        migrations.RunPython(replace_value_vocucher_type),
        migrations.AlterField(
            model_name="voucher",
            name="type",
            field=models.CharField(
                choices=[
                    ("entire_order", "Entire order"),
                    ("room", "Specific rooms"),
                    ("collection", "Specific collections of rooms"),
                    ("category", "Specific categories of rooms"),
                    ("shipping", "Shipping"),
                    (
                        "specific_room",
                        "Specific rooms, collections and categories",
                    ),
                ],
                default="entire_order",
                max_length=20,
            ),
        ),
    ]