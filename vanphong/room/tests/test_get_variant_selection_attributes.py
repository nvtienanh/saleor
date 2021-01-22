from ...attribute import AttributeInputType
from ..utils.variants import get_variant_selection_attributes


def test_get_variant_selection_attributes(
    room_type_attribute_list,
    file_attribute_with_file_input_type_without_values,
    room_type_page_reference_attribute,
    room_type_room_reference_attribute,
):
    # given
    multiselect_attr = room_type_attribute_list[0]
    multiselect_attr.input_type = AttributeInputType.MULTISELECT
    multiselect_attr.save(update_fields=["input_type"])

    attrs = room_type_attribute_list + [
        file_attribute_with_file_input_type_without_values,
        room_type_page_reference_attribute,
        room_type_room_reference_attribute,
    ]

    # when
    result = get_variant_selection_attributes(attrs)

    # then
    assert result == room_type_attribute_list[1:]
