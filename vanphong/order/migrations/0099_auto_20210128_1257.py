# Generated by Django 3.1.5 on 2021-01-28 05:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0098_remove_order_weight'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='order',
            name='shipping_address',
        ),
        migrations.RemoveField(
            model_name='order',
            name='shipping_method',
        ),
        migrations.RemoveField(
            model_name='order',
            name='shipping_method_name',
        ),
        migrations.RemoveField(
            model_name='order',
            name='shipping_price_gross_amount',
        ),
        migrations.RemoveField(
            model_name='order',
            name='shipping_price_net_amount',
        ),
        migrations.RemoveField(
            model_name='order',
            name='shipping_tax_rate',
        ),
        migrations.RemoveField(
            model_name='orderline',
            name='is_shipping_required',
        ),
    ]
