from unittest.mock import patch

from ..models import Category
from ..utils import collect_categories_tree_rooms, delete_categories


def test_collect_categories_tree_rooms(categories_tree):
    parent = categories_tree
    child = parent.children.first()
    rooms = parent.rooms.all() | child.rooms.all()

    result = collect_categories_tree_rooms(parent)

    assert len(result) == len(rooms)
    assert set(result.values_list("pk", flat=True)) == set(
        rooms.values_list("pk", flat=True)
    )


@patch("saleor.room.utils.update_rooms_discounted_prices_task")
def test_delete_categories(
    mock_update_rooms_discounted_prices_task,
    categories_tree_with_published_rooms,
):
    parent = categories_tree_with_published_rooms
    child = parent.children.first()
    room_list = [child.rooms.first(), parent.rooms.first()]

    delete_categories([parent.pk])

    assert not Category.objects.filter(
        id__in=[category.id for category in [parent, child]]
    ).exists()

    calls = mock_update_rooms_discounted_prices_task.mock_calls
    assert len(calls) == 1
    call_kwargs = calls[0].kwargs
    assert set(call_kwargs["room_ids"]) == {p.pk for p in room_list}

    for room in room_list:
        room.refresh_from_db()
        assert not room.category
        for room_channel_listing in room.channel_listings.all():
            assert not room_channel_listing.is_published
            assert not room_channel_listing.publication_date
