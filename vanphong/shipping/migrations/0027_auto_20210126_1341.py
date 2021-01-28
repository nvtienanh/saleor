# Generated by Django 3.1.5 on 2021-01-26 06:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shipping', '0026_shippingzone_description'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='shippingmethod',
            name='maximum_order_weight',
        ),
        migrations.RemoveField(
            model_name='shippingmethod',
            name='minimum_order_weight',
        ),
        migrations.AlterField(
            model_name='shippingmethod',
            name='type',
            field=models.CharField(choices=[('price', 'Price based shipping')], max_length=30),
        ),
    ]