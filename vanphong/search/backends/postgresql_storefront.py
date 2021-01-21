from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q

from ...room.models import Room


def search(phrase):
    """Return matching rooms for storefront views.

    Fuzzy storefront search that is resistant to small typing errors made
    by user. Name is matched using trigram similarity, description uses
    standard postgres full text search.

    Args:
        phrase (str): searched phrase

    """
    name_sim = TrigramSimilarity("name", phrase)
    ft_in_description = Q(description__search=phrase)
    ft_by_sku = Q(variants__sku__search=phrase)
    name_similar = Q(name_sim__gt=0.2)
    return Room.objects.annotate(name_sim=name_sim).filter(
        (ft_in_description | name_similar | ft_by_sku)
    )
