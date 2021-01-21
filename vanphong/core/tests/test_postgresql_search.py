import pytest
from django.utils.text import slugify

from ...account.models import Address
from ...room.models import Room, RoomChannelListing
from ...search.backends.postgresql import search_storefront

ROOMS = [
    ("Arabica Coffee", "The best grains in galactic"),
    ("Cool T-Shirt", "Blue and big."),
    ("Roasted chicken", "Fabulous vertebrate"),
]


@pytest.fixture
def named_rooms(category, room_type, channel_USD):
    def gen_room(name, description):
        room = Room.objects.create(
            name=name,
            slug=slugify(name),
            description=description,
            room_type=room_type,
            category=category,
        )
        RoomChannelListing.objects.create(
            room=room,
            channel=channel_USD,
            is_published=True,
        )
        return room

    return [gen_room(name, desc) for name, desc in ROOMS]


def execute_search(phrase):
    """Execute storefront search."""
    return search_storefront(phrase)


@pytest.mark.parametrize(
    "phrase,room_num",
    [
        ("Arabika", 0),
        ("Aarabica", 0),
        ("Arab", 0),
        ("czicken", 2),
        ("blue", 1),
        ("roast", 2),
        ("coool", 1),
    ],
)
@pytest.mark.integration
@pytest.mark.django_db
def test_storefront_room_fuzzy_name_search(named_rooms, phrase, room_num):
    results = execute_search(phrase)
    assert 1 == len(results)
    assert named_rooms[room_num] in results


USERS = [
    ("Andreas", "Knop", "adreas.knop@example.com"),
    ("Euzebiusz", "Ziemniak", "euzeb.potato@cebula.pl"),
    ("John", "Doe", "johndoe@example.com"),
]
ORDER_IDS = [10, 45, 13]
ORDERS = [[pk] + list(user) for pk, user in zip(ORDER_IDS, USERS)]


def gen_address_for_user(first_name, last_name):
    return Address.objects.create(
        first_name=first_name,
        last_name=last_name,
        company_name="Mirumee Software",
        street_address_1="Tęczowa 7",
        city="Wrocław",
        postal_code="53-601",
        country="PL",
    )
