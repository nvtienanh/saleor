class ShippingMethodType:
    PRICE_BASED = "price"
    # WEIGHT_BASED = "weight"

    CHOICES = [
        (PRICE_BASED, "Price based shipping"),
        # TODO: Remove fields related `weight`
        # (WEIGHT_BASED, "Weight based shipping"),
    ]
