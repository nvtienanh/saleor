from saleor.webhook.payload_serializers import PythonSerializer


def test_python_serializer_extra_model_fields(room_with_single_variant):
    serializer = PythonSerializer(
        extra_model_fields={"RoomVariant": ("quantity", "quantity_allocated")}
    )
    annotated_variant = (
        room_with_single_variant.variants.annotate_quantities().first()
    )
    serializer._current = {"test_item": "test_value"}
    result = serializer.get_dump_object(annotated_variant)
    assert result["type"] == "RoomVariant"
    assert result["test_item"] == "test_value"
    assert result["quantity"] == str(annotated_variant.quantity)
    assert result["quantity_allocated"] == str(annotated_variant.quantity_allocated)


def test_python_serializer_extra_model_fields_incorrect_fields(
    room_with_single_variant,
):
    serializer = PythonSerializer(
        extra_model_fields={
            "NonExistingModel": ("__dummy",),
            "RoomVariant": ("__not_on_model",),
        }
    )
    annotated_variant = (
        room_with_single_variant.variants.annotate_quantities().first()
    )
    serializer._current = {"test_item": "test_value"}
    result = serializer.get_dump_object(annotated_variant)
    assert result["type"] == "RoomVariant"
    assert result["test_item"] == "test_value"
