from django.contrib.postgres.fields import jsonb
from django.core import exceptions
from django.db import migrations, models


def validate_attribute_json(value):
    for k, values in value.items():
        if not isinstance(k, str):
            raise exceptions.ValidationError(
                f"The key {k!r} should be of type str (got {type(k)})",
                params={"k": k, "values": values},
            )
        if not isinstance(values, list):
            raise exceptions.ValidationError(
                f"The values of {k!r} should be of type list (got {type(values)})",
                params={"k": k, "values": values},
            )

        for value_pk in values:
            if not isinstance(value_pk, str):
                raise exceptions.ValidationError(
                    f"The values inside {value_pk!r} should be of type str "
                    f"(got {type(value_pk)})",
                    params={"k": k, "values": values, "value_pk": value_pk},
                )


def migrate_fk_to_m2m(room_type_related_field):
    """Migrate room types' foreign key to a M2M relation."""

    def make_migration(apps, schema):
        RoomType = apps.get_model("room", "RoomType")

        for room_type in RoomType.objects.all():
            m2m_field = getattr(room_type, room_type_related_field)
            attributes_to_migrate = getattr(
                room_type, f"{room_type_related_field}_old"
            )
            for attr in attributes_to_migrate.all():
                if room_type not in m2m_field.all():
                    m2m_field.add(attr)

    return make_migration


ROOM_TYPE_UNIQUE_SLUGS = [
    migrations.AlterField(
        model_name="attribute", name="slug", field=models.SlugField(unique=True)
    )
]

ATTRIBUTE_NEW_FIELDS = [
    migrations.AddField(
        model_name="attribute",
        name="input_type",
        field=models.CharField(
            choices=[("dropdown", "Dropdown"), ("multiselect", "Multi Select")],
            default="dropdown",
            max_length=50,
        ),
    ),
    migrations.AlterField(
        model_name="room",
        name="attributes",
        field=jsonb.JSONField(
            blank=True, default=dict, validators=[validate_attribute_json]
        ),
    ),
    migrations.AlterField(
        model_name="roomvariant",
        name="attributes",
        field=jsonb.JSONField(
            blank=True, default=dict, validators=[validate_attribute_json]
        ),
    ),
    migrations.AddField(
        model_name="attribute",
        name="available_in_grid",
        field=models.BooleanField(blank=True, default=True),
    ),
    migrations.AddField(
        model_name="attribute",
        name="visible_in_storefront",
        field=models.BooleanField(default=True, blank=True),
    ),
    migrations.AddField(
        model_name="attribute",
        name="filterable_in_dashboard",
        field=models.BooleanField(default=True, blank=True),
    ),
    migrations.AddField(
        model_name="attribute",
        name="filterable_in_storefront",
        field=models.BooleanField(default=True, blank=True),
    ),
    migrations.AddField(
        model_name="attribute",
        name="value_required",
        field=models.BooleanField(default=False, blank=True),
    ),
    migrations.AddField(
        model_name="attribute",
        name="storefront_search_position",
        field=models.IntegerField(default=0, blank=True),
    ),
    migrations.AlterModelOptions(
        name="attribute", options={"ordering": ("storefront_search_position", "slug")}
    ),
]

ROOM_TYPE_NEW_RELATION = [
    migrations.AddField(
        model_name="attribute",
        name="is_variant_only",
        field=models.BooleanField(default=False, blank=True),
    ),
    # Rename the foreign keys to backup them before overriding and processing them
    migrations.RenameField(
        model_name="attribute", old_name="room_type", new_name="room_type_old"
    ),
    migrations.RenameField(
        model_name="attribute",
        old_name="room_variant_type",
        new_name="room_variant_type_old",
    ),
    # Rename related names of foreign keys
    migrations.AlterField(
        model_name="attribute",
        name="room_type_old",
        field=models.ForeignKey(
            blank=True,
            null=True,
            on_delete=models.deletion.CASCADE,
            related_name="room_attributes_old",
            to="room.RoomType",
        ),
    ),
    migrations.AlterField(
        model_name="attribute",
        name="room_variant_type_old",
        field=models.ForeignKey(
            blank=True,
            null=True,
            on_delete=models.deletion.CASCADE,
            related_name="variant_attributes_old",
            to="room.RoomType",
        ),
    ),
    # Add the M2M new fields
    migrations.CreateModel(
        name="AttributeRoom",
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
            (
                "attribute",
                models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name="attributeroom",
                    to="room.Attribute",
                ),
            ),
            (
                "room_type",
                models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name="attributeroom",
                    to="room.RoomType",
                ),
            ),
            (
                "sort_order",
                models.IntegerField(db_index=True, editable=False, null=True),
            ),
        ],
        options={"abstract": False},
    ),
    migrations.CreateModel(
        name="AttributeVariant",
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
            (
                "attribute",
                models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name="attributevariant",
                    to="room.Attribute",
                ),
            ),
            (
                "room_type",
                models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name="attributevariant",
                    to="room.RoomType",
                ),
            ),
            (
                "sort_order",
                models.IntegerField(db_index=True, editable=False, null=True),
            ),
        ],
        options={"abstract": False},
    ),
    migrations.AddField(
        model_name="attribute",
        name="room_types",
        field=models.ManyToManyField(
            blank=True,
            related_name="room_attributes",
            through="room.AttributeRoom",
            to="room.RoomType",
        ),
    ),
    migrations.AddField(
        model_name="attribute",
        name="room_variant_types",
        field=models.ManyToManyField(
            blank=True,
            related_name="variant_attributes",
            through="room.AttributeVariant",
            to="room.RoomType",
        ),
    ),
    # Migrate the foreign keys into M2M
    migrations.RunPython(migrate_fk_to_m2m("room_attributes")),
    migrations.RunPython(migrate_fk_to_m2m("variant_attributes")),
    # Remove the migrated foreign keys
    migrations.RemoveField(model_name="attribute", name="room_variant_type_old"),
    migrations.RemoveField(model_name="attribute", name="room_type_old"),
]

SORTING_NULLABLE_LOGIC = [
    migrations.AlterField(
        model_name="attributevalue",
        name="sort_order",
        field=models.IntegerField(db_index=True, editable=False, null=True),
    ),
    migrations.AlterField(
        model_name="collectionroom",
        name="sort_order",
        field=models.IntegerField(db_index=True, editable=False, null=True),
    ),
    migrations.AlterField(
        model_name="roomimage",
        name="sort_order",
        field=models.IntegerField(db_index=True, editable=False, null=True),
    ),
    migrations.AlterModelOptions(
        name="attributevalue", options={"ordering": ("sort_order", "id")}
    ),
]

M2M_UNIQUE_TOGETHER = [
    migrations.AlterUniqueTogether(
        name="attributeroom", unique_together={("attribute", "room_type")}
    ),
    migrations.AlterUniqueTogether(
        name="attributevariant", unique_together={("attribute", "room_type")}
    ),
    migrations.AlterUniqueTogether(
        name="collectionroom", unique_together={("collection", "room")}
    ),
]


class Migration(migrations.Migration):

    dependencies = [("room", "0102_migrate_data_enterprise_grade_attributes")]

    operations = (
        ROOM_TYPE_UNIQUE_SLUGS
        + ATTRIBUTE_NEW_FIELDS
        + ROOM_TYPE_NEW_RELATION
        + SORTING_NULLABLE_LOGIC
        + M2M_UNIQUE_TOGETHER
    )
