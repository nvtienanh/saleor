# Generated by Django 2.2.9 on 2020-01-29 06:50

from collections import defaultdict

from django.db import migrations, models
from django.db.models.functions import Lower
from django.utils.text import slugify


def create_unique_slugs_for_roomtypes(apps, schema_editor):
    RoomType = apps.get_model("room", "RoomType")

    room_types = (
        RoomType.objects.filter(slug__isnull=True).order_by(Lower("name")).iterator()
    )
    previous_char = ""
    slug_values = []
    for room_type in room_types:
        first_char = room_type.name[0].lower()
        if first_char != previous_char:
            previous_char = first_char
            slug_values = list(
                RoomType.objects.filter(slug__istartswith=first_char).values_list(
                    "slug", flat=True
                )
            )

        slug = generate_unique_slug(room_type, slug_values)
        room_type.slug = slug
        room_type.save(update_fields=["slug"])
        slug_values.append(slug)


def generate_unique_slug(instance, slug_values_list):
    slug = slugify(instance.name)
    unique_slug = slug

    extension = 1

    while unique_slug in slug_values_list:
        extension += 1
        unique_slug = f"{slug}-{extension}"

    return unique_slug


def update_non_unique_slugs_for_models(apps, schema_editor):
    models_to_update = ["Category", "Collection"]

    for model in models_to_update:
        Model = apps.get_model("room", model)

        duplicated_slugs = (
            Model.objects.all()
            .values("slug")
            .annotate(duplicated_slug_num=models.Count("slug"))
            .filter(duplicated_slug_num__gt=1)
        )

        slugs_counter = defaultdict(int)
        for data in duplicated_slugs:
            slugs_counter[data["slug"]] = data["duplicated_slug_num"]

        queryset = Model.objects.filter(slug__in=slugs_counter.keys()).order_by("name")

        for instance in queryset:
            slugs_counter[instance.slug] -= 1
            slug = update_slug_to_unique_value(instance.slug, slugs_counter)
            instance.slug = slug
            instance.save(update_fields=["slug"])
            slugs_counter[slug] += 1


def update_slug_to_unique_value(slug_value, slugs_counter):
    unique_slug = slug_value
    extension = 1

    while unique_slug in slugs_counter and slugs_counter[unique_slug] > 0:
        extension += 1
        unique_slug = f"{slug_value}-{extension}"

    return unique_slug


class Migration(migrations.Migration):

    dependencies = [
        ("room", "0111_auto_20191209_0437"),
    ]

    operations = [
        migrations.RunPython(
            update_non_unique_slugs_for_models, migrations.RunPython.noop
        ),
        migrations.AddField(
            model_name="roomtype",
            name="slug",
            field=models.SlugField(null=True, max_length=128, unique=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="category",
            name="slug",
            field=models.SlugField(max_length=128, unique=True),
        ),
        migrations.AlterField(
            model_name="collection",
            name="slug",
            field=models.SlugField(max_length=128, unique=True),
        ),
        migrations.RunPython(
            create_unique_slugs_for_roomtypes, migrations.RunPython.noop
        ),
        migrations.AlterField(
            model_name="roomtype",
            name="slug",
            field=models.SlugField(max_length=128, unique=True),
        ),
    ]
