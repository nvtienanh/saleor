from unittest.mock import patch

from freezegun import freeze_time
from graphql_relay import from_global_id, to_global_id

from ...discount.enums import DiscountValueTypeEnum
from ...tests.utils import get_graphql_content


@patch("saleor.graphql.room.mutations.rooms.update_room_discounted_price_task")
def test_room_variant_delete_updates_discounted_price(
    mock_update_room_discounted_price_task,
    staff_api_client,
    room,
    permission_manage_rooms,
):
    query = """
        mutation RoomVariantDelete($id: ID!) {
            roomVariantDelete(id: $id) {
                roomVariant {
                    id
                }
                errors {
                    field
                    message
                }
              }
            }
    """
    variant = room.variants.first()
    variant_id = to_global_id("RoomVariant", variant.pk)
    variables = {"id": variant_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["roomVariantDelete"]
    assert data["errors"] == []

    mock_update_room_discounted_price_task.delay.assert_called_once_with(room.pk)


@patch("saleor.room.utils.update_rooms_discounted_prices_task")
def test_category_delete_updates_discounted_price(
    mock_update_rooms_discounted_prices_task,
    staff_api_client,
    categories_tree_with_published_rooms,
    permission_manage_rooms,
):
    parent = categories_tree_with_published_rooms
    room_list = [parent.children.first().rooms.first(), parent.rooms.first()]

    query = """
        mutation CategoryDelete($id: ID!) {
            categoryDelete(id: $id) {
                category {
                    name
                }
                errors {
                    field
                    message
                }
            }
        }
    """
    variables = {"id": to_global_id("Category", parent.pk)}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    assert response.status_code == 200

    content = get_graphql_content(response)
    data = content["data"]["categoryDelete"]
    assert data["errors"] == []

    mock_update_rooms_discounted_prices_task.delay.assert_called_once()
    (
        _call_args,
        call_kwargs,
    ) = mock_update_rooms_discounted_prices_task.delay.call_args
    assert set(call_kwargs["room_ids"]) == set(p.pk for p in room_list)

    for room in room_list:
        room.refresh_from_db()
        assert not room.category


@patch(
    "saleor.graphql.room.mutations.rooms"
    ".update_rooms_discounted_prices_of_catalogues_task"
)
def test_collection_add_rooms_updates_discounted_price(
    mock_update_rooms_discounted_prices_of_catalogues,
    staff_api_client,
    sale,
    collection,
    room_list,
    permission_manage_rooms,
):
    sale.collections.add(collection)
    assert collection.rooms.count() == 0
    query = """
        mutation CollectionAddRooms($id: ID!, $rooms: [ID]!) {
            collectionAddRooms(collectionId: $id, rooms: $rooms) {
                collection {
                    rooms {
                        totalCount
                    }
                }
                errors {
                    field
                    message
                }
            }
        }
    """
    collection_id = to_global_id("Collection", collection.id)
    room_ids = [to_global_id("Room", room.pk) for room in room_list]
    variables = {"id": collection_id, "rooms": room_ids}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["collectionAddRooms"]
    assert data["errors"] == []

    mock_update_rooms_discounted_prices_of_catalogues.delay.assert_called_once_with(
        room_ids=[p.pk for p in room_list]
    )


@patch(
    "saleor.graphql.room.mutations"
    ".rooms.update_rooms_discounted_prices_of_catalogues_task"
)
def test_collection_remove_rooms_updates_discounted_price(
    mock_update_rooms_discounted_prices_of_catalogues,
    staff_api_client,
    sale,
    collection,
    room_list,
    permission_manage_rooms,
):
    sale.collections.add(collection)
    assert collection.rooms.count() == 0
    query = """
        mutation CollectionRemoveRooms($id: ID!, $rooms: [ID]!) {
            collectionRemoveRooms(collectionId: $id, rooms: $rooms) {
                collection {
                    rooms {
                        totalCount
                    }
                }
                errors {
                    field
                    message
                }
            }
        }
    """
    collection_id = to_global_id("Collection", collection.id)
    room_ids = [to_global_id("Room", room.pk) for room in room_list]
    variables = {"id": collection_id, "rooms": room_ids}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["collectionRemoveRooms"]
    assert data["errors"] == []

    mock_update_rooms_discounted_prices_of_catalogues.delay.assert_called_once_with(
        room_ids=[p.pk for p in room_list]
    )


@freeze_time("2010-05-31 12:00:01")
@patch(
    "saleor.graphql.discount.mutations"
    ".update_rooms_discounted_prices_of_discount_task"
)
def test_sale_create_updates_rooms_discounted_prices(
    mock_update_rooms_discounted_prices_of_catalogues,
    staff_api_client,
    permission_manage_discounts,
):
    query = """
    mutation SaleCreate(
            $name: String,
            $type: DiscountValueTypeEnum,
            $value: PositiveDecimal,
            $rooms: [ID]
    ) {
        saleCreate(input: {
                name: $name,
                type: $type,
                value: $value,
                rooms: $rooms
        }) {
            sale {
                id
            }
            errors {
                field
                message
            }
        }
    }
    """
    variables = {
        "name": "Half price room",
        "type": DiscountValueTypeEnum.PERCENTAGE.name,
        "value": "50",
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_discounts]
    )
    assert response.status_code == 200

    content = get_graphql_content(response)
    assert content["data"]["saleCreate"]["errors"] == []

    relay_sale_id = content["data"]["saleCreate"]["sale"]["id"]
    _sale_class_name, sale_id_str = from_global_id(relay_sale_id)
    sale_id = int(sale_id_str)
    mock_update_rooms_discounted_prices_of_catalogues.delay.assert_called_once_with(
        sale_id
    )


@patch(
    "saleor.graphql.discount.mutations"
    ".update_rooms_discounted_prices_of_discount_task"
)
def test_sale_update_updates_rooms_discounted_prices(
    mock_update_rooms_discounted_prices_of_discount,
    staff_api_client,
    sale,
    permission_manage_discounts,
):
    query = """
    mutation SaleUpdate($id: ID!, $value: PositiveDecimal) {
        saleUpdate(id: $id, input: {value: $value}) {
            sale {
                id
            }
            errors {
                field
                message
            }
        }
    }
    """
    variables = {"id": to_global_id("Sale", sale.pk), "value": "99"}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_discounts]
    )
    assert response.status_code == 200

    content = get_graphql_content(response)
    assert content["data"]["saleUpdate"]["errors"] == []

    mock_update_rooms_discounted_prices_of_discount.delay.assert_called_once_with(
        sale.pk
    )


@patch(
    "saleor.graphql.discount.mutations"
    ".update_rooms_discounted_prices_of_discount_task"
)
def test_sale_delete_updates_rooms_discounted_prices(
    mock_update_rooms_discounted_prices_of_discount,
    staff_api_client,
    sale,
    permission_manage_discounts,
):
    query = """
    mutation SaleDelete($id: ID!) {
        saleDelete(id: $id) {
            sale {
                id
            }
            errors {
                field
                message
            }
        }
    }
    """
    variables = {"id": to_global_id("Sale", sale.pk)}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_discounts]
    )
    assert response.status_code == 200

    content = get_graphql_content(response)
    assert content["data"]["saleDelete"]["errors"] == []

    mock_update_rooms_discounted_prices_of_discount.delay.assert_called_once_with(
        sale.pk
    )


@patch(
    "saleor.graphql.discount.mutations"
    ".update_rooms_discounted_prices_of_catalogues_task"
)
def test_sale_add_catalogues_updates_rooms_discounted_prices(
    mock_update_rooms_discounted_prices_of_catalogues,
    staff_api_client,
    sale,
    room,
    category,
    collection,
    permission_manage_discounts,
):
    query = """
        mutation SaleCataloguesAdd($id: ID!, $input: CatalogueInput!) {
            saleCataloguesAdd(id: $id, input: $input) {
                sale {
                    name
                }
                discountErrors {
                    field
                    message
                }
            }
        }
    """
    sale_id = to_global_id("Sale", sale.pk)
    room_id = to_global_id("Room", room.pk)
    collection_id = to_global_id("Collection", collection.pk)
    category_id = to_global_id("Category", category.pk)
    variables = {
        "id": sale_id,
        "input": {
            "rooms": [room_id],
            "collections": [collection_id],
            "categories": [category_id],
        },
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_discounts]
    )
    assert response.status_code == 200

    content = get_graphql_content(response)
    assert not content["data"]["saleCataloguesAdd"]["discountErrors"]

    mock_update_rooms_discounted_prices_of_catalogues.delay.assert_called_once_with(
        room_ids=[room.pk],
        category_ids=[category.pk],
        collection_ids=[collection.pk],
    )


@patch(
    "saleor.graphql.discount.mutations"
    ".update_rooms_discounted_prices_of_catalogues_task"
)
def test_sale_remove_catalogues_updates_rooms_discounted_prices(
    mock_update_rooms_discounted_prices_of_catalogues,
    staff_api_client,
    sale,
    room,
    category,
    collection,
    permission_manage_discounts,
):
    assert room in sale.rooms.all()
    assert category in sale.categories.all()
    assert collection in sale.collections.all()
    query = """
        mutation SaleCataloguesRemove($id: ID!, $input: CatalogueInput!) {
            saleCataloguesRemove(id: $id, input: $input) {
                sale {
                    name
                }
                discountErrors {
                    field
                    message
                }
            }
        }
    """
    sale_id = to_global_id("Sale", sale.pk)
    room_id = to_global_id("Room", room.pk)
    collection_id = to_global_id("Collection", collection.pk)
    category_id = to_global_id("Category", category.pk)
    variables = {
        "id": sale_id,
        "input": {
            "rooms": [room_id],
            "collections": [collection_id],
            "categories": [category_id],
        },
    }

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_discounts]
    )
    assert response.status_code == 200

    content = get_graphql_content(response)
    assert not content["data"]["saleCataloguesRemove"]["discountErrors"]

    mock_update_rooms_discounted_prices_of_catalogues.delay.assert_called_once_with(
        room_ids=[room.pk],
        category_ids=[category.pk],
        collection_ids=[collection.pk],
    )
