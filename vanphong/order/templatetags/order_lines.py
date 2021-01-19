from django import template

from ..models import OrderLine

register = template.Library()


@register.simple_tag()
def display_translated_order_line_name(order_line: OrderLine):
    room_name = order_line.translated_room_name or order_line.room_name
    variant_name = order_line.translated_variant_name or order_line.variant_name
    return f"{room_name} ({variant_name})" if variant_name else room_name
