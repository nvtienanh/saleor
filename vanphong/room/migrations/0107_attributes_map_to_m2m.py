# Generated by Django 2.2.4 on 2019-08-19 12:02
from django.db import migrations, models


def migrate_room_attribute_map_to_m2m(apps, schema):
    """Migrate the JSONB attribute map to a M2M relation."""
    Room = apps.get_model("room", "Room")
    AssignedRoomAttribute = apps.get_model("room", "AssignedRoomAttribute")
    room_qs = Room.objects.prefetch_related(
        "room_type__attributeroom__attribute__values"
    )

    for room in room_qs:
        attribute_map = room.old_attributes

        # Skip if no attribute is assigned to this room
        if not attribute_map:
            continue

        room_type = room.room_type

        for attribute_pk, values_pk in attribute_map.items():
            attribute_rel = room_type.attributeroom.filter(
                attribute_id=attribute_pk
            ).first()

            # Skip the assigned attribute if it is not assigned to the room type
            if attribute_rel is None:
                continue

            values = list(attribute_rel.attribute.values.filter(pk__in=values_pk))

            # If no values are associated, skip
            if not values:
                continue

            assignment = AssignedRoomAttribute.objects.create(
                room=room, assignment=attribute_rel
            )
            assignment.values.set(values)


def migrate_variant_attribute_map_to_m2m(apps, schema):
    """Migrate the JSONB attribute map to a M2M relation."""
    RoomVariant = apps.get_model("room", "RoomVariant")
    AssignedVariantAttribute = apps.get_model("room", "AssignedVariantAttribute")
    variants_qs = RoomVariant.objects.prefetch_related(
        "room__room_type__attributevariant__attribute__values"
    )

    for variant in variants_qs:
        attribute_map = variant.old_attributes

        # Skip if no attribute is assigned to this variant
        if not attribute_map:
            continue

        room_type = variant.room.room_type

        for attribute_pk, values_pk in attribute_map.items():
            attribute_rel = room_type.attributevariant.filter(
                attribute_id=attribute_pk
            ).first()

            # Skip the assigned attribute if it is not assigned to the room type
            if attribute_rel is None:
                continue

            values = list(attribute_rel.attribute.values.filter(pk__in=values_pk))

            # If no values are associated, skip
            if not values:
                continue

            assignment = AssignedVariantAttribute.objects.create(
                variant=variant, assignment=attribute_rel
            )
            assignment.values.set(values)


class Migration(migrations.Migration):

    dependencies = [("room", "0106_django_prices_2")]

    operations = [
        # Temporary renaming of the attribute map to migrate the data
        migrations.RenameField(
            model_name="room", old_name="attributes", new_name="old_attributes"
        ),
        migrations.RenameField(
            model_name="roomvariant",
            old_name="attributes",
            new_name="old_attributes",
        ),
        # Add the new attribute relation instead of the JSONB mapping
        migrations.CreateModel(
            name="AssignedRoomAttribute",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("values", models.ManyToManyField(to="room.AttributeValue")),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="attributes",
                        to="room.Room",
                    ),
                ),
                (
                    "assignment",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="roomassignments",
                        to="room.AttributeRoom",
                    ),
                ),
            ],
            options={"unique_together": {("room", "assignment")}},
        ),
        migrations.CreateModel(
            name="AssignedVariantAttribute",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("values", models.ManyToManyField(to="room.AttributeValue")),
                (
                    "variant",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="attributes",
                        to="room.RoomVariant",
                    ),
                ),
                (
                    "assignment",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="variantassignments",
                        to="room.AttributeVariant",
                    ),
                ),
            ],
            options={"unique_together": {("variant", "assignment")}},
        ),
        migrations.AddField(
            model_name="attributeroom",
            name="assigned_rooms",
            field=models.ManyToManyField(
                blank=True,
                through="room.AssignedRoomAttribute",
                to="room.Room",
                related_name="attributesrelated",
            ),
        ),
        migrations.AddField(
            model_name="attributevariant",
            name="assigned_variants",
            field=models.ManyToManyField(
                blank=True,
                through="room.AssignedVariantAttribute",
                to="room.RoomVariant",
                related_name="attributesrelated",
            ),
        ),
        migrations.AlterModelOptions(
            name="attributeroom", options={"ordering": ("sort_order",)}
        ),
        migrations.AlterModelOptions(
            name="attributevariant", options={"ordering": ("sort_order",)}
        ),
        # Migrate the JSONB mapping to M2M
        migrations.RunPython(migrate_room_attribute_map_to_m2m),
        migrations.RunPython(migrate_variant_attribute_map_to_m2m),
        # Remove the JSONB mapping
        migrations.RemoveField(model_name="room", name="old_attributes"),
        migrations.RemoveField(model_name="roomvariant", name="old_attributes"),
    ]