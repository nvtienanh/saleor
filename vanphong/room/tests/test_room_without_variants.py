from ..utils import get_rooms_ids_without_variants


def test_get_rooms_ids_without_variants(room_list):
    assert get_rooms_ids_without_variants(room_list) == []

    room = room_list[0]
    room.variants.all().delete()

    second_room = room_list[1]
    second_room.variants.all().delete()

    assert get_rooms_ids_without_variants(room_list) == [
        room.id,
        second_room.id,
    ]
