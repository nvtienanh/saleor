from ..models import Stock

COUNTRY_CODE = "US"


def test_stocks_for_country(variant_with_many_stocks):
    [stock1, stock2] = (
        Stock.objects.filter(room_variant=variant_with_many_stocks)
        .for_country(COUNTRY_CODE)
        .order_by("pk")
        .all()
    )
    hotel1 = stock1.hotel
    hotel2 = stock2.hotel
    assert stock1.quantity == 4
    assert COUNTRY_CODE in hotel1.countries
    assert stock2.quantity == 3
    assert COUNTRY_CODE in hotel2.countries


def test_stock_for_country_does_not_exists(room, hotel):
    shipping_zone = hotel.shipping_zones.first()
    shipping_zone.countries = [COUNTRY_CODE]
    shipping_zone.save(update_fields=["countries"])
    hotel.refresh_from_db()
    fake_country_code = "PL"
    assert fake_country_code not in hotel.countries
    stock_qs = Stock.objects.for_country(fake_country_code)
    assert not stock_qs.exists()
