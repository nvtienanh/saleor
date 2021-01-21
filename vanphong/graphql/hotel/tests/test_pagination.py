import graphene
import pytest

from ....hotel.models import Hotel
from ...tests.utils import get_graphql_content


@pytest.fixture
def hotels_for_pagination(db, address):
    return Hotel.objects.bulk_create(
        [
            Hotel(
                name="Hotel1",
                address=address,
                slug="w1",
            ),
            Hotel(
                name="HotelHotel1",
                address=address,
                slug="ww1",
            ),
            Hotel(
                name="HotelHotel2",
                address=address,
                slug="ww2",
            ),
            Hotel(
                name="Hotel2",
                address=address,
                slug="w2",
            ),
            Hotel(
                name="Hotel3",
                address=address,
                slug="w3",
            ),
        ]
    )


QUERY_HOTELS_PAGINATION = """
    query (
        $first: Int, $last: Int, $after: String, $before: String,
        $sortBy: HotelSortingInput, $filter: HotelFilterInput
    ){
        hotels(
            first: $first, last: $last, after: $after, before: $before,
            sortBy: $sortBy, filter: $filter
        ) {
            edges {
                node {
                    name
                }
            }
            pageInfo{
                startCursor
                endCursor
                hasNextPage
                hasPreviousPage
            }
        }
    }
"""


@pytest.mark.parametrize(
    "sort_by, hotels_order",
    [
        (
            {"field": "NAME", "direction": "ASC"},
            ["Hotel1", "Hotel2", "Hotel3"],
        ),
        (
            {"field": "NAME", "direction": "DESC"},
            ["HotelHotel2", "HotelHotel1", "Hotel3"],
        ),
    ],
)
def test_hotels_pagination_with_sorting(
    sort_by,
    hotels_order,
    staff_api_client,
    permission_manage_rooms,
    hotels_for_pagination,
):
    page_size = 3

    variables = {"first": page_size, "after": None, "sortBy": sort_by}
    response = staff_api_client.post_graphql(
        QUERY_HOTELS_PAGINATION, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    hotels_nodes = content["data"]["hotels"]["edges"]
    assert hotels_order[0] == hotels_nodes[0]["node"]["name"]
    assert hotels_order[1] == hotels_nodes[1]["node"]["name"]
    assert hotels_order[2] == hotels_nodes[2]["node"]["name"]
    assert len(hotels_nodes) == page_size


@pytest.mark.parametrize(
    "filter_by, hotels_order",
    [
        (
            {"search": "HotelHotel"},
            ["HotelHotel2", "HotelHotel1"],
        ),
        ({"search": "Hotel1"}, ["HotelHotel1", "Hotel1"]),
    ],
)
def test_hotels_pagination_with_filtering(
    filter_by,
    hotels_order,
    staff_api_client,
    permission_manage_rooms,
    hotels_for_pagination,
):
    page_size = 2

    variables = {"first": page_size, "after": None, "filter": filter_by}
    response = staff_api_client.post_graphql(
        QUERY_HOTELS_PAGINATION, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    hotels_nodes = content["data"]["hotels"]["edges"]
    assert hotels_order[0] == hotels_nodes[0]["node"]["name"]
    assert hotels_order[1] == hotels_nodes[1]["node"]["name"]
    assert len(hotels_nodes) == page_size


def test_hotels_pagination_with_filtering_by_id(
    staff_api_client,
    permission_manage_rooms,
    hotels_for_pagination,
):
    page_size = 2
    hotels_order = ["HotelHotel2", "HotelHotel1"]
    hotels_ids = [
        graphene.Node.to_global_id("Hotel", hotel.pk)
        for hotel in hotels_for_pagination
    ]
    filter_by = {"ids": hotels_ids}

    variables = {"first": page_size, "after": None, "filter": filter_by}
    response = staff_api_client.post_graphql(
        QUERY_HOTELS_PAGINATION, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    hotels_nodes = content["data"]["hotels"]["edges"]
    assert hotels_order[0] == hotels_nodes[0]["node"]["name"]
    assert hotels_order[1] == hotels_nodes[1]["node"]["name"]
    assert len(hotels_nodes) == page_size
