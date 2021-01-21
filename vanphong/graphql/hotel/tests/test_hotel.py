import graphene
import pytest

from ....account.models import Address
from ....hotel.error_codes import HotelErrorCode
from ....hotel.models import Hotel
from ...tests.utils import assert_no_permission, get_graphql_content

QUERY_HOTELS = """
query {
    hotels(first:100) {
        totalCount
        edges {
            node {
                id
                name
                companyName
                email
                shippingZones(first:100) {
                    edges {
                        node {
                            name
                            countries {
                                country
                            }
                        }
                    }
                }
                address {
                    city
                    postalCode
                    country {
                        country
                    }
                    phone
                }
            }
        }
    }
}
"""

QUERY_HOTELS_WITH_FILTERS = """
query Hotels($filters: HotelFilterInput) {
    hotels(first:100, filter: $filters) {
        totalCount
        edges {
            node {
                id
                name
                companyName
                email
            }
        }
    }
}
"""

QUERY_WERHOUSES_WITH_FILTERS_NO_IDS = """
query Hotels($filters: HotelFilterInput) {
    hotels(first:100, filter: $filters) {
        totalCount
        edges {
            node {
                name
                companyName
                email
            }
        }
    }
}
"""

QUERY_HOTEL = """
query hotel($id: ID!){
    hotel(id: $id) {
        id
        name
        companyName
        email
        shippingZones(first: 100) {
            edges {
                node {
                    name
                    countries {
                        country
                    }
                }
            }
        }
        address {
            streetAddress1
            streetAddress2
            postalCode
            city
            phone
        }
    }
}
"""


MUTATION_CREATE_HOTEL = """
mutation createHotel($input: HotelCreateInput!) {
    createHotel(input: $input){
        hotel {
            id
            name
            slug
            companyName
            address {
                id
            }
        }
        hotelErrors {
            message
            field
            code
        }
    }
}
"""


MUTATION_UPDATE_HOTEL = """
mutation updateHotel($input: HotelUpdateInput!, $id: ID!) {
    updateHotel(id: $id, input: $input) {
        hotelErrors {
            message
            field
            code
        }
        hotel {
            name
            slug
            companyName
            address {
                id
                streetAddress1
                streetAddress2
            }
        }
    }
}
"""


MUTATION_DELETE_HOTEL = """
mutation deleteHotel($id: ID!) {
    deleteHotel(id: $id) {
        hotelErrors {
            message
            field
            code
        }
    }
}
"""


MUTATION_ASSIGN_SHIPPING_ZONE_HOTEL = """
mutation assignHotelShippingZone($id: ID!, $shippingZoneIds: [ID!]!) {
  assignHotelShippingZone(id: $id, shippingZoneIds: $shippingZoneIds) {
    hotelErrors {
      field
      message
      code
    }
  }
}

"""


MUTATION_UNASSIGN_SHIPPING_ZONE_HOTEL = """
mutation unassignHotelShippingZone($id: ID!, $shippingZoneIds: [ID!]!) {
  unassignHotelShippingZone(id: $id, shippingZoneIds: $shippingZoneIds) {
    hotelErrors {
      field
      message
      code
    }
  }
}

"""


def test_hotel_query(staff_api_client, hotel, permission_manage_rooms):
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.pk)

    response = staff_api_client.post_graphql(
        QUERY_HOTEL,
        variables={"id": hotel_id},
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)

    queried_hotel = content["data"]["hotel"]
    assert queried_hotel["name"] == hotel.name
    assert queried_hotel["email"] == hotel.email

    shipping_zones = queried_hotel["shippingZones"]["edges"]
    assert len(shipping_zones) == hotel.shipping_zones.count()
    queried_shipping_zone = shipping_zones[0]["node"]
    shipipng_zone = hotel.shipping_zones.first()
    assert queried_shipping_zone["name"] == shipipng_zone.name
    assert len(queried_shipping_zone["countries"]) == len(shipipng_zone.countries)

    address = hotel.address
    queried_address = queried_hotel["address"]
    assert queried_address["streetAddress1"] == address.street_address_1
    assert queried_address["postalCode"] == address.postal_code


def test_hotel_query_as_staff_with_manage_orders(
    staff_api_client, hotel, permission_manage_orders
):
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.pk)

    response = staff_api_client.post_graphql(
        QUERY_HOTEL,
        variables={"id": hotel_id},
        permissions=[permission_manage_orders],
    )
    content = get_graphql_content(response)

    queried_hotel = content["data"]["hotel"]
    assert queried_hotel["name"] == hotel.name
    assert queried_hotel["email"] == hotel.email

    shipping_zones = queried_hotel["shippingZones"]["edges"]
    assert len(shipping_zones) == hotel.shipping_zones.count()
    queried_shipping_zone = shipping_zones[0]["node"]
    shipipng_zone = hotel.shipping_zones.first()
    assert queried_shipping_zone["name"] == shipipng_zone.name
    assert len(queried_shipping_zone["countries"]) == len(shipipng_zone.countries)

    address = hotel.address
    queried_address = queried_hotel["address"]
    assert queried_address["streetAddress1"] == address.street_address_1
    assert queried_address["postalCode"] == address.postal_code


def test_hotel_query_as_staff_with_manage_apps(
    staff_api_client, hotel, permission_manage_apps
):
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.pk)

    response = staff_api_client.post_graphql(
        QUERY_HOTEL,
        variables={"id": hotel_id},
        permissions=[permission_manage_apps],
    )

    assert_no_permission(response)


def test_hotel_query_as_customer(user_api_client, hotel):
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.pk)

    response = user_api_client.post_graphql(
        QUERY_HOTEL,
        variables={"id": hotel_id},
    )

    assert_no_permission(response)


def test_query_hotels_as_staff_with_manage_orders(
    staff_api_client, hotel, permission_manage_orders
):
    response = staff_api_client.post_graphql(
        QUERY_HOTELS, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)["data"]
    assert content["hotels"]["totalCount"] == Hotel.objects.count()
    hotels = content["hotels"]["edges"]
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.pk)
    hotel_first = hotels[0]["node"]
    assert hotel_first["id"] == hotel_id
    assert hotel_first["name"] == hotel.name
    assert (
        len(hotel_first["shippingZones"]["edges"])
        == hotel.shipping_zones.count()
    )


def test_query_hotels_as_staff_with_manage_apps(
    staff_api_client, hotel, permission_manage_apps
):
    response = staff_api_client.post_graphql(
        QUERY_HOTELS, permissions=[permission_manage_apps]
    )
    assert_no_permission(response)


def test_query_hotels_as_customer(
    user_api_client, hotel, permission_manage_apps
):
    response = user_api_client.post_graphql(QUERY_HOTELS)
    assert_no_permission(response)


def test_query_hotels(staff_api_client, hotel, permission_manage_rooms):
    response = staff_api_client.post_graphql(
        QUERY_HOTELS, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)["data"]
    assert content["hotels"]["totalCount"] == Hotel.objects.count()
    hotels = content["hotels"]["edges"]
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.pk)
    hotel_first = hotels[0]["node"]
    assert hotel_first["id"] == hotel_id
    assert hotel_first["name"] == hotel.name
    assert (
        len(hotel_first["shippingZones"]["edges"])
        == hotel.shipping_zones.count()
    )


def test_query_hotels_with_filters_name(
    staff_api_client, permission_manage_rooms, hotel
):
    variables_exists = {"filters": {"search": "hotel"}}
    response = staff_api_client.post_graphql(
        QUERY_HOTELS_WITH_FILTERS,
        variables=variables_exists,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.id)
    content_hotel = content["data"]["hotels"]["edges"][0]["node"]
    assert content_hotel["id"] == hotel_id
    variables_does_not_exists = {"filters": {"search": "Absolutelywrong name"}}
    response1 = staff_api_client.post_graphql(
        QUERY_HOTELS_WITH_FILTERS, variables=variables_does_not_exists
    )
    content1 = get_graphql_content(response1)
    total_count = content1["data"]["hotels"]["totalCount"]
    assert total_count == 0


def test_query_hotel_with_filters_email(
    staff_api_client, permission_manage_rooms, hotel
):
    variables_exists = {"filters": {"search": "test"}}
    response_exists = staff_api_client.post_graphql(
        QUERY_HOTELS_WITH_FILTERS,
        variables=variables_exists,
        permissions=[permission_manage_rooms],
    )
    content_exists = get_graphql_content(response_exists)
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.id)
    content_hotel = content_exists["data"]["hotels"]["edges"][0]["node"]
    assert content_hotel["id"] == hotel_id

    variable_does_not_exists = {"filters": {"search": "Bad@email.pl"}}
    response_not_exists = staff_api_client.post_graphql(
        QUERY_HOTELS_WITH_FILTERS, variables=variable_does_not_exists
    )
    content_not_exists = get_graphql_content(response_not_exists)
    total_count = content_not_exists["data"]["hotels"]["totalCount"]
    assert total_count == 0


def test_query_hotel_with_filters_by_ids(
    staff_api_client, permission_manage_rooms, hotel, hotel_no_shipping_zone
):
    hotel_ids = [
        graphene.Node.to_global_id("Hotel", hotel.id),
        graphene.Node.to_global_id("Hotel", hotel_no_shipping_zone.id),
    ]
    variables_exists = {"filters": {"ids": hotel_ids}}
    response_exists = staff_api_client.post_graphql(
        QUERY_HOTELS_WITH_FILTERS,
        variables=variables_exists,
        permissions=[permission_manage_rooms],
    )
    content_exists = get_graphql_content(response_exists)

    content_hotels = content_exists["data"]["hotels"]["edges"]
    for content_hotel in content_hotels:
        assert content_hotel["node"]["id"] in hotel_ids
    assert content_exists["data"]["hotels"]["totalCount"] == 2


def test_query_hotel_with_filters_by_id(
    staff_api_client, permission_manage_rooms, hotel, hotel_no_shipping_zone
):
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.id)
    variables_exists = {"filters": {"ids": [hotel_id]}}
    response_exists = staff_api_client.post_graphql(
        QUERY_HOTELS_WITH_FILTERS,
        variables=variables_exists,
        permissions=[permission_manage_rooms],
    )
    content_exists = get_graphql_content(response_exists)

    content_hotels = content_exists["data"]["hotels"]["edges"]
    assert content_hotels[0]["node"]["id"] == hotel_id
    assert content_exists["data"]["hotels"]["totalCount"] == 1


def test_query_hotels_with_filters_and_no_id(
    staff_api_client, permission_manage_rooms, hotel
):
    variables_exists = {"filters": {"search": "test"}}
    response_exists = staff_api_client.post_graphql(
        QUERY_HOTELS_WITH_FILTERS,
        variables=variables_exists,
        permissions=[permission_manage_rooms],
    )
    content_exists = get_graphql_content(response_exists)
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.id)
    content_hotel = content_exists["data"]["hotels"]["edges"][0]["node"]
    assert content_hotel["id"] == hotel_id

    variable_does_not_exists = {"filters": {"search": "Bad@email.pl"}}
    response_not_exists = staff_api_client.post_graphql(
        QUERY_HOTELS_WITH_FILTERS, variables=variable_does_not_exists
    )
    content_not_exists = get_graphql_content(response_not_exists)
    total_count = content_not_exists["data"]["hotels"]["totalCount"]
    assert total_count == 0


def test_mutation_create_hotel(
    staff_api_client, permission_manage_rooms, shipping_zone
):
    variables = {
        "input": {
            "name": "Test hotel",
            "slug": "test-warhouse",
            "companyName": "Amazing Company Inc",
            "email": "test-admin@example.com",
            "address": {
                "streetAddress1": "Teczowa 8",
                "city": "Wroclaw",
                "country": "PL",
                "postalCode": "53-601",
            },
            "shippingZones": [
                graphene.Node.to_global_id("ShippingZone", shipping_zone.id)
            ],
        }
    }

    response = staff_api_client.post_graphql(
        MUTATION_CREATE_HOTEL,
        variables=variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    assert Hotel.objects.count() == 1
    hotel = Hotel.objects.first()
    created_hotel = content["data"]["createHotel"]["hotel"]
    assert created_hotel["id"] == graphene.Node.to_global_id(
        "Hotel", hotel.id
    )
    assert created_hotel["name"] == hotel.name
    assert created_hotel["slug"] == hotel.slug


def test_mutation_create_hotel_does_not_create_when_name_is_empty_string(
    staff_api_client, permission_manage_rooms, shipping_zone
):
    variables = {
        "input": {
            "name": "  ",
            "slug": "test-warhouse",
            "companyName": "Amazing Company Inc",
            "email": "test-admin@example.com",
            "address": {
                "streetAddress1": "Teczowa 8",
                "city": "Wroclaw",
                "country": "PL",
                "postalCode": "53-601",
            },
            "shippingZones": [
                graphene.Node.to_global_id("ShippingZone", shipping_zone.id)
            ],
        }
    }

    response = staff_api_client.post_graphql(
        MUTATION_CREATE_HOTEL,
        variables=variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    data = content["data"]["createHotel"]
    errors = data["hotelErrors"]
    assert Hotel.objects.count() == 0
    assert len(errors) == 1
    assert errors[0]["field"] == "name"
    assert errors[0]["code"] == HotelErrorCode.REQUIRED.name


def test_create_hotel_creates_address(
    staff_api_client, permission_manage_rooms, shipping_zone
):
    variables = {
        "input": {
            "name": "Test hotel",
            "companyName": "Amazing Company Inc",
            "email": "test-admin@example.com",
            "address": {
                "streetAddress1": "Teczowa 8",
                "city": "Wroclaw",
                "country": "PL",
                "postalCode": "53-601",
            },
            "shippingZones": [
                graphene.Node.to_global_id("ShippingZone", shipping_zone.id)
            ],
        }
    }
    assert not Address.objects.exists()
    response = staff_api_client.post_graphql(
        MUTATION_CREATE_HOTEL,
        variables=variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    errors = content["data"]["createHotel"]["hotelErrors"]
    assert len(errors) == 0
    assert Address.objects.count() == 1
    address = Address.objects.get(street_address_1="Teczowa 8", city="WROCLAW")
    address_id = graphene.Node.to_global_id("Address", address.id)
    hotel_data = content["data"]["createHotel"]["hotel"]
    assert hotel_data["address"]["id"] == address_id
    assert address.street_address_1 == "Teczowa 8"
    assert address.city == "WROCLAW"


@pytest.mark.parametrize(
    "input_slug, expected_slug",
    (
        ("test-slug", "test-slug"),
        (None, "test-hotel"),
        ("", "test-hotel"),
    ),
)
def test_create_hotel_with_given_slug(
    staff_api_client, permission_manage_rooms, input_slug, expected_slug
):
    query = MUTATION_CREATE_HOTEL
    name = "Test hotel"
    variables = {"name": name, "slug": input_slug}
    variables = {
        "input": {
            "name": name,
            "slug": input_slug,
            "address": {
                "streetAddress1": "Teczowa 8",
                "city": "Wroclaw",
                "country": "PL",
                "postalCode": "53-601",
            },
        }
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["createHotel"]
    assert not data["hotelErrors"]
    assert data["hotel"]["slug"] == expected_slug


def test_mutation_update_hotel(
    staff_api_client, hotel, permission_manage_rooms
):
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.id)
    hotel_old_name = hotel.name
    hotel_slug = hotel.slug
    hotel_old_company_name = hotel.company_name
    variables = {
        "id": hotel_id,
        "input": {"name": "New name", "companyName": "New name for company"},
    }
    staff_api_client.post_graphql(
        MUTATION_UPDATE_HOTEL,
        variables=variables,
        permissions=[permission_manage_rooms],
    )
    hotel.refresh_from_db()
    assert not (hotel.name == hotel_old_name)
    assert not (hotel.company_name == hotel_old_company_name)
    assert hotel.name == "New name"
    assert hotel.slug == hotel_slug
    assert hotel.company_name == "New name for company"


def test_mutation_update_hotel_can_update_address(
    staff_api_client, hotel, permission_manage_rooms
):
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.pk)
    address_id = graphene.Node.to_global_id("Address", hotel.address.pk)
    address = hotel.address
    variables = {
        "id": hotel_id,
        "input": {
            "name": hotel.name,
            "companyName": "",
            "address": {
                "streetAddress1": "Teczowa 8",
                "streetAddress2": "Ground floor",
                "city": address.city,
                "country": address.country.code,
                "postalCode": "53-601",
            },
        },
    }
    response = staff_api_client.post_graphql(
        MUTATION_UPDATE_HOTEL,
        variables=variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    content_address = content["data"]["updateHotel"]["hotel"]["address"]
    assert content_address["id"] == address_id
    address.refresh_from_db()
    assert address.street_address_1 == "Teczowa 8"
    assert address.street_address_2 == "Ground floor"


@pytest.mark.parametrize(
    "input_slug, expected_slug, error_message",
    [
        ("test-slug", "test-slug", None),
        ("", "", "Slug value cannot be blank."),
        (None, "", "Slug value cannot be blank."),
    ],
)
def test_update_hotel_slug(
    staff_api_client,
    hotel,
    permission_manage_rooms,
    input_slug,
    expected_slug,
    error_message,
):
    query = MUTATION_UPDATE_HOTEL
    old_slug = hotel.slug

    assert old_slug != input_slug

    node_id = graphene.Node.to_global_id("Hotel", hotel.id)
    variables = {"id": node_id, "input": {"slug": input_slug}}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["updateHotel"]
    errors = data["hotelErrors"]
    if not error_message:
        assert not errors
        assert data["hotel"]["slug"] == expected_slug
    else:
        assert errors
        assert errors[0]["field"] == "slug"
        assert errors[0]["code"] == HotelErrorCode.REQUIRED.name


def test_update_hotel_slug_exists(
    staff_api_client, hotel, permission_manage_rooms
):
    query = MUTATION_UPDATE_HOTEL
    input_slug = "test-slug"

    second_hotel = Hotel.objects.get(pk=hotel.pk)
    second_hotel.pk = None
    second_hotel.slug = input_slug
    second_hotel.save()

    assert input_slug != hotel.slug

    node_id = graphene.Node.to_global_id("Hotel", hotel.id)
    variables = {"id": node_id, "input": {"slug": input_slug}}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    data = content["data"]["updateHotel"]
    errors = data["hotelErrors"]
    assert errors
    assert errors[0]["field"] == "slug"
    assert errors[0]["code"] == HotelErrorCode.UNIQUE.name


@pytest.mark.parametrize(
    "input_slug, expected_slug, input_name, expected_name, error_message, error_field",
    [
        ("test-slug", "test-slug", "New name", "New name", None, None),
        (
            "test-slug",
            "test-slug",
            " stripped ",
            "stripped",
            None,
            None,
        ),
        ("", "", "New name", "New name", "Slug value cannot be blank.", "slug"),
        (None, "", "New name", "New name", "Slug value cannot be blank.", "slug"),
        ("test-slug", "", None, None, "This field cannot be blank.", "name"),
        ("test-slug", "", "", None, "This field cannot be blank.", "name"),
        (None, None, None, None, "Slug value cannot be blank.", "slug"),
        ("test-slug", "test-slug", "  ", None, "Name value cannot be blank", "name"),
    ],
)
def test_update_hotel_slug_and_name(
    staff_api_client,
    hotel,
    permission_manage_rooms,
    input_slug,
    expected_slug,
    input_name,
    expected_name,
    error_message,
    error_field,
):
    query = MUTATION_UPDATE_HOTEL

    old_name = hotel.name
    old_slug = hotel.slug

    assert input_slug != old_slug
    assert input_name != old_name

    node_id = graphene.Node.to_global_id("Hotel", hotel.id)
    variables = {"input": {"slug": input_slug, "name": input_name}, "id": node_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_rooms]
    )
    content = get_graphql_content(response)
    hotel.refresh_from_db()
    data = content["data"]["updateHotel"]
    errors = data["hotelErrors"]
    if not error_message:
        assert data["hotel"]["name"] == expected_name == hotel.name
        assert (
            data["hotel"]["slug"] == input_slug == hotel.slug == expected_slug
        )
    else:
        assert errors
        assert errors[0]["field"] == error_field
        assert errors[0]["code"] == HotelErrorCode.REQUIRED.name


def test_delete_hotel_mutation(
    staff_api_client, hotel, permission_manage_rooms
):
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.pk)
    assert Hotel.objects.count() == 1
    response = staff_api_client.post_graphql(
        MUTATION_DELETE_HOTEL,
        variables={"id": hotel_id},
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    errors = content["data"]["deleteHotel"]["hotelErrors"]
    assert len(errors) == 0
    assert not Hotel.objects.exists()


def test_delete_hotel_deletes_associated_address(
    staff_api_client, hotel, permission_manage_rooms
):
    hotel_id = graphene.Node.to_global_id("Hotel", hotel.pk)
    assert Address.objects.count() == 1
    response = staff_api_client.post_graphql(
        MUTATION_DELETE_HOTEL,
        variables={"id": hotel_id},
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    errors = content["data"]["deleteHotel"]["hotelErrors"]
    assert len(errors) == 0
    assert not Address.objects.exists()


def test_shipping_zone_can_be_assigned_only_to_one_hotel(
    staff_api_client, hotel, permission_manage_rooms
):
    used_shipping_zone = hotel.shipping_zones.first()
    used_shipping_zone_id = graphene.Node.to_global_id(
        "ShippingZone", used_shipping_zone.pk
    )

    variables = {
        "input": {
            "name": "Hotel #q",
            "companyName": "Big Company",
            "email": "test@example.com",
            "address": {
                "streetAddress1": "Teczowa 8",
                "city": "Wroclaw",
                "country": "PL",
                "postalCode": "53-601",
            },
            "shippingZones": [used_shipping_zone_id],
        }
    }

    response = staff_api_client.post_graphql(
        MUTATION_CREATE_HOTEL,
        variables=variables,
        permissions=[permission_manage_rooms],
    )
    content = get_graphql_content(response)
    errors = content["data"]["createHotel"]["hotelErrors"]
    assert len(errors) == 1
    assert (
        errors[0]["message"] == "Shipping zone can be assigned only to one hotel."
    )
    used_shipping_zone.refresh_from_db()
    assert used_shipping_zone.hotels.count() == 1


def test_shipping_zone_assign_to_hotel(
    staff_api_client,
    hotel_no_shipping_zone,
    shipping_zone,
    permission_manage_rooms,
):
    assert not hotel_no_shipping_zone.shipping_zones.all()
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    variables = {
        "id": graphene.Node.to_global_id("Hotel", hotel_no_shipping_zone.pk),
        "shippingZoneIds": [
            graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
        ],
    }

    staff_api_client.post_graphql(
        MUTATION_ASSIGN_SHIPPING_ZONE_HOTEL, variables=variables
    )
    hotel_no_shipping_zone.refresh_from_db()
    shipping_zone.refresh_from_db()
    assert hotel_no_shipping_zone.shipping_zones.first().pk == shipping_zone.pk


def test_empty_shipping_zone_assign_to_hotel(
    staff_api_client,
    hotel_no_shipping_zone,
    shipping_zone,
    permission_manage_rooms,
):
    assert not hotel_no_shipping_zone.shipping_zones.all()
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    variables = {
        "id": graphene.Node.to_global_id("Hotel", hotel_no_shipping_zone.pk),
        "shippingZoneIds": [],
    }

    response = staff_api_client.post_graphql(
        MUTATION_ASSIGN_SHIPPING_ZONE_HOTEL, variables=variables
    )
    content = get_graphql_content(response)
    errors = content["data"]["assignHotelShippingZone"]["hotelErrors"]
    hotel_no_shipping_zone.refresh_from_db()
    shipping_zone.refresh_from_db()

    assert not hotel_no_shipping_zone.shipping_zones.all()
    assert errors[0]["field"] == "shippingZoneId"
    assert errors[0]["code"] == "GRAPHQL_ERROR"


def test_shipping_zone_unassign_from_hotel(
    staff_api_client, hotel, shipping_zone, permission_manage_rooms
):
    assert hotel.shipping_zones.first().pk == shipping_zone.pk
    staff_api_client.user.user_permissions.add(permission_manage_rooms)
    variables = {
        "id": graphene.Node.to_global_id("Hotel", hotel.pk),
        "shippingZoneIds": [
            graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
        ],
    }

    staff_api_client.post_graphql(
        MUTATION_UNASSIGN_SHIPPING_ZONE_HOTEL, variables=variables
    )
    hotel.refresh_from_db()
    shipping_zone.refresh_from_db()
    assert not hotel.shipping_zones.all()
