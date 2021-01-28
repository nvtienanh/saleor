from .....attribute import AttributeInputType


def add_room_attribute_data_to_expected_data(data, room, attribute_ids, pk=None):
    for assigned_attribute in room.attributes.all():
        if assigned_attribute:
            header = f"{assigned_attribute.attribute.slug} (room attribute)"
            if str(assigned_attribute.attribute.pk) in attribute_ids:
                value = get_attribute_value(assigned_attribute)
                if pk:
                    data[pk][header] = value
                else:
                    data[header] = value
    return data


def add_variant_attribute_data_to_expected_data(data, variant, attribute_ids, pk=None):
    for assigned_attribute in variant.attributes.all():
        header = f"{assigned_attribute.attribute.slug} (variant attribute)"
        if str(assigned_attribute.attribute.pk) in attribute_ids:
            value = get_attribute_value(assigned_attribute)
            if pk:
                data[pk][header] = value
            else:
                data[header] = value

    return data


def get_attribute_value(assigned_attribute):
    value_instance = assigned_attribute.values.first()
    attribute = assigned_attribute.attribute
    if attribute.input_type == AttributeInputType.FILE:
        value = value_instance.file_url
    elif attribute.input_type == AttributeInputType.REFERENCE:
        ref_id = value_instance.slug.split("_")[1]
        value = f"{attribute.entity_type}_{ref_id}"
    else:
        value = value_instance.slug
    return value


def add_stocks_to_expected_data(data, variant, hotel_ids, pk=None):
    for stock in variant.stocks.all():
        if str(stock.hotel.pk) in hotel_ids:
            slug = stock.hotel.slug
            hotel_headers = [
                f"{slug} (hotel quantity)",
            ]
            if pk:
                data[pk][hotel_headers[0]] = stock.quantity
            else:
                data[hotel_headers[0]] = stock.quantity

    return data


def add_channel_to_expected_room_data(data, room, channel_ids, pk=None):
    for channel_listing in room.channel_listings.all():
        if str(channel_listing.channel.pk) in channel_ids:
            channel_slug = channel_listing.channel.slug
            for lookup, field in [
                ("currency_code", "room currency code"),
                ("is_published", "published"),
                ("publication_date", "publication date"),
                ("visible_in_listings", "searchable"),
                ("available_for_purchase", "available for purchase"),
            ]:
                header = f"{channel_slug} (channel {field})"
                if lookup == "currency_code":
                    value = getattr(channel_listing, "currency")
                else:
                    value = getattr(channel_listing, lookup)
                if pk:
                    data[pk][header] = value
                else:
                    data[header] = value

    return data


def add_channel_to_expected_variant_data(data, variant, channel_ids, pk=None):
    for channel_listing in variant.channel_listings.all():
        if str(channel_listing.channel.pk) in channel_ids:
            channel_slug = channel_listing.channel.slug
            price_header = f"{channel_slug} (channel price amount)"
            currency_header = f"{channel_slug} (channel variant currency code)"
            cost_price = f"{channel_slug} (channel variant cost price)"
            if pk:
                data[pk][price_header] = channel_listing.price_amount
                data[pk][currency_header] = channel_listing.currency
                data[pk][cost_price] = channel_listing.cost_price_amount
            else:
                data[price_header] = channel_listing.price_amount
                data[currency_header] = channel_listing.currency
                data[cost_price] = channel_listing.cost_price_amount
    return data