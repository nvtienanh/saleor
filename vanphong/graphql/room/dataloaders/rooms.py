from collections import defaultdict
from typing import DefaultDict, Dict, Iterable, List, Optional, Tuple

from django.db.models import F

from ....room.models import (
    Category,
    Collection,
    CollectionChannelListing,
    CollectionRoom,
    Room,
    RoomChannelListing,
    RoomImage,
    RoomType,
    RoomVariant,
    RoomVariantChannelListing,
    VariantImage,
)
from ...core.dataloaders import DataLoader

RoomIdAndChannelSlug = Tuple[int, str]
VariantIdAndChannelSlug = Tuple[int, str]


class CategoryByIdLoader(DataLoader):
    context_key = "category_by_id"

    def batch_load(self, keys):
        categories = Category.objects.in_bulk(keys)
        return [categories.get(category_id) for category_id in keys]


class RoomByIdLoader(DataLoader):
    context_key = "room_by_id"

    def batch_load(self, keys):
        rooms = Room.objects.all().in_bulk(keys)
        return [rooms.get(room_id) for room_id in keys]


class RoomByVariantIdLoader(DataLoader):
    context_key = "room_by_variant_id"

    def batch_load(self, keys):
        def with_variants(variants):
            room_ids = [variant.room_id for variant in variants]
            return RoomByIdLoader(self.context).load_many(room_ids)

        return (
            RoomVariantByIdLoader(self.context).load_many(keys).then(with_variants)
        )


class RoomChannelListingByIdLoader(DataLoader[int, RoomChannelListing]):
    context_key = "roomchannelisting_by_id"

    def batch_load(self, keys):
        room_channel_listings = RoomChannelListing.objects.in_bulk(keys)
        return [room_channel_listings.get(key) for key in keys]


class RoomChannelListingByRoomIdLoader(DataLoader[int, RoomChannelListing]):
    context_key = "roomchannelisting_by_room"

    def batch_load(self, keys):
        room_channel_listings = RoomChannelListing.objects.filter(
            room_id__in=keys
        )
        room_id_variant_channel_listings_map = defaultdict(list)
        for room_channel_listing in room_channel_listings:
            room_id_variant_channel_listings_map[
                room_channel_listing.room_id
            ].append(room_channel_listing)
        return [
            room_id_variant_channel_listings_map.get(room_id, [])
            for room_id in keys
        ]


class RoomChannelListingByRoomIdAndChannelSlugLoader(
    DataLoader[RoomIdAndChannelSlug, RoomChannelListing]
):
    context_key = "roomchannelisting_by_room_and_channel"

    def batch_load(self, keys):
        # Split the list of keys by channel first. A typical query will only touch
        # a handful of unique countries but may access thousands of room variants
        # so it's cheaper to execute one query per channel.
        room_channel_listing_by_channel: DefaultDict[str, List[int]] = defaultdict(
            list
        )
        for room_id, channel_slug in keys:
            room_channel_listing_by_channel[channel_slug].append(room_id)

        # For each channel execute a single query for all rooms.
        room_channel_listing_by_room_and_channel: DefaultDict[
            RoomIdAndChannelSlug, Optional[RoomChannelListing]
        ] = defaultdict()
        for channel_slug, room_ids in room_channel_listing_by_channel.items():
            room_channel_listings = self.batch_load_channel(
                channel_slug, room_ids
            )
            for room_id, room_channel_listing in room_channel_listings:
                room_channel_listing_by_room_and_channel[
                    (room_id, channel_slug)
                ] = room_channel_listing

        return [room_channel_listing_by_room_and_channel[key] for key in keys]

    def batch_load_channel(
        self, channel_slug: str, rooms_ids: Iterable[int]
    ) -> Iterable[Tuple[int, Optional[RoomChannelListing]]]:
        room_channel_listings = RoomChannelListing.objects.filter(
            channel__slug=channel_slug, room_id__in=rooms_ids
        )

        room_channel_listings_map: Dict[int, RoomChannelListing] = {}
        for room_channel_listing in room_channel_listings.iterator():
            room_channel_listings_map[
                room_channel_listing.room_id
            ] = room_channel_listing

        return [
            (rooms_id, room_channel_listings_map.get(rooms_id))
            for rooms_id in rooms_ids
        ]


class RoomTypeByIdLoader(DataLoader):
    context_key = "room_type_by_id"

    def batch_load(self, keys):
        room_types = RoomType.objects.in_bulk(keys)
        return [room_types.get(room_type_id) for room_type_id in keys]


class ImagesByRoomIdLoader(DataLoader):
    context_key = "images_by_room"

    def batch_load(self, keys):
        images = RoomImage.objects.filter(room_id__in=keys)
        image_map = defaultdict(list)
        for image in images:
            image_map[image.room_id].append(image)
        return [image_map[room_id] for room_id in keys]


class RoomVariantByIdLoader(DataLoader):
    context_key = "roomvariant_by_id"

    def batch_load(self, keys):
        variants = RoomVariant.objects.in_bulk(keys)
        return [variants.get(key) for key in keys]


class RoomVariantsByRoomIdLoader(DataLoader):
    context_key = "roomvariants_by_room"

    def batch_load(self, keys):
        variants = RoomVariant.objects.filter(room_id__in=keys)
        variant_map = defaultdict(list)
        variant_loader = RoomVariantByIdLoader(self.context)
        for variant in variants.iterator():
            variant_map[variant.room_id].append(variant)
            variant_loader.prime(variant.id, variant)
        return [variant_map.get(room_id, []) for room_id in keys]


class RoomVariantChannelListingByIdLoader(DataLoader):
    context_key = "roomvariantchannelisting_by_id"

    def batch_load(self, keys):
        variants = RoomVariantChannelListing.objects.in_bulk(keys)
        return [variants.get(key) for key in keys]


class VariantChannelListingByVariantIdLoader(DataLoader):
    context_key = "roomvariantchannelisting_by_roomvariant"

    def batch_load(self, keys):
        variant_channel_listings = RoomVariantChannelListing.objects.filter(
            variant_id__in=keys
        )
        variant_id_variant_channel_listings_map = defaultdict(list)
        for variant_channel_listing in variant_channel_listings:
            variant_id_variant_channel_listings_map[
                variant_channel_listing.variant_id
            ].append(variant_channel_listing)
        return [
            variant_id_variant_channel_listings_map.get(variant_id, [])
            for variant_id in keys
        ]


class VariantChannelListingByVariantIdAndChannelSlugLoader(
    DataLoader[VariantIdAndChannelSlug, RoomVariantChannelListing]
):
    context_key = "variantchannelisting_by_variant_and_channel"

    def batch_load(self, keys):
        # Split the list of keys by channel first. A typical query will only touch
        # a handful of unique countries but may access thousands of room variants
        # so it's cheaper to execute one query per channel.
        variant_channel_listing_by_channel: DefaultDict[str, List[int]] = defaultdict(
            list
        )
        for variant_id, channel_slug in keys:
            variant_channel_listing_by_channel[channel_slug].append(variant_id)

        # For each channel execute a single query for all room variants.
        variant_channel_listing_by_variant_and_channel: DefaultDict[
            VariantIdAndChannelSlug, Optional[RoomVariantChannelListing]
        ] = defaultdict()
        for channel_slug, variant_ids in variant_channel_listing_by_channel.items():
            variant_channel_listings = self.batch_load_channel(
                channel_slug, variant_ids
            )
            for variant_id, variant_channel_listing in variant_channel_listings:
                variant_channel_listing_by_variant_and_channel[
                    (variant_id, channel_slug)
                ] = variant_channel_listing

        return [variant_channel_listing_by_variant_and_channel[key] for key in keys]

    def batch_load_channel(
        self, channel_slug: str, variant_ids: Iterable[int]
    ) -> Iterable[Tuple[int, Optional[RoomVariantChannelListing]]]:
        variant_channel_listings = RoomVariantChannelListing.objects.filter(
            channel__slug=channel_slug, variant_id__in=variant_ids
        )

        variant_channel_listings_map: Dict[int, RoomVariantChannelListing] = {}
        for variant_channel_listing in variant_channel_listings.iterator():
            variant_channel_listings_map[
                variant_channel_listing.variant_id
            ] = variant_channel_listing

        return [
            (variant_id, variant_channel_listings_map.get(variant_id))
            for variant_id in variant_ids
        ]


class VariantsChannelListingByRoomIdAndChanneSlugLoader(
    DataLoader[RoomIdAndChannelSlug, Iterable[RoomVariantChannelListing]]
):
    context_key = "variantschannelisting_by_room_and_channel"

    def batch_load(self, keys):
        # Split the list of keys by channel first. A typical query will only touch
        # a handful of unique countries but may access thousands of room variants
        # so it's cheaper to execute one query per channel.
        variant_channel_listing_by_channel: DefaultDict[str, List[int]] = defaultdict(
            list
        )
        for room_id, channel_slug in keys:
            variant_channel_listing_by_channel[channel_slug].append(room_id)

        # For each channel execute a single query for all room variants.
        variant_channel_listing_by_room_and_channel: DefaultDict[
            RoomIdAndChannelSlug, Optional[Iterable[RoomVariantChannelListing]]
        ] = defaultdict()
        for channel_slug, room_ids in variant_channel_listing_by_channel.items():
            varaint_channel_listings = self.batch_load_channel(
                channel_slug, room_ids
            )
            for room_id, variants_channel_listing in varaint_channel_listings:
                variant_channel_listing_by_room_and_channel[
                    (room_id, channel_slug)
                ] = variants_channel_listing

        return [
            variant_channel_listing_by_room_and_channel.get(key, []) for key in keys
        ]

    def batch_load_channel(
        self, channel_slug: str, rooms_ids: Iterable[int]
    ) -> Iterable[Tuple[int, Optional[List[RoomVariantChannelListing]]]]:
        variants_channel_listings = RoomVariantChannelListing.objects.filter(
            channel__slug=channel_slug, variant__room_id__in=rooms_ids
        ).annotate(room_id=F("variant__room_id"))

        variants_channel_listings_map: Dict[
            int, List[RoomVariantChannelListing]
        ] = defaultdict(list)
        for variant_channel_listing in variants_channel_listings.iterator():
            variants_channel_listings_map[variant_channel_listing.room_id].append(
                variant_channel_listing
            )

        return [
            (rooms_id, variants_channel_listings_map.get(rooms_id, []))
            for rooms_id in rooms_ids
        ]


class RoomImageByIdLoader(DataLoader):
    context_key = "room_image_by_id"

    def batch_load(self, keys):
        room_images = RoomImage.objects.in_bulk(keys)
        return [room_images.get(room_image_id) for room_image_id in keys]


class ImagesByRoomVariantIdLoader(DataLoader):
    context_key = "images_by_room_variant"

    def batch_load(self, keys):
        variant_images = VariantImage.objects.filter(variant_id__in=keys).values_list(
            "variant_id", "image_id"
        )

        variant_image_pairs = defaultdict(list)
        for variant_id, image_id in variant_images:
            variant_image_pairs[variant_id].append(image_id)

        def map_variant_images(images):
            images_map = {image.id: image for image in images}
            return [
                [images_map[image_id] for image_id in variant_image_pairs[variant_id]]
                for variant_id in keys
            ]

        return (
            RoomImageByIdLoader(self.context)
            .load_many(set(image_id for variant_id, image_id in variant_images))
            .then(map_variant_images)
        )


class CollectionByIdLoader(DataLoader):
    context_key = "collection_by_id"

    def batch_load(self, keys):
        collections = Collection.objects.in_bulk(keys)
        return [collections.get(collection_id) for collection_id in keys]


class CollectionsByRoomIdLoader(DataLoader):
    context_key = "collections_by_room"

    def batch_load(self, keys):
        room_collection_pairs = list(
            CollectionRoom.objects.filter(room_id__in=keys)
            .order_by("id")
            .values_list("room_id", "collection_id")
        )
        room_collection_map = defaultdict(list)
        for pid, cid in room_collection_pairs:
            room_collection_map[pid].append(cid)

        def map_collections(collections):
            collection_map = {c.id: c for c in collections}
            return [
                [collection_map[cid] for cid in room_collection_map[pid]]
                for pid in keys
            ]

        return (
            CollectionByIdLoader(self.context)
            .load_many(set(cid for pid, cid in room_collection_pairs))
            .then(map_collections)
        )


class CollectionsByVariantIdLoader(DataLoader):
    context_key = "collections_by_variant"

    def batch_load(self, keys):
        def with_variants(variants):
            room_ids = [variant.room_id for variant in variants]
            return CollectionsByRoomIdLoader(self.context).load_many(room_ids)

        return (
            RoomVariantByIdLoader(self.context).load_many(keys).then(with_variants)
        )


class RoomTypeByRoomIdLoader(DataLoader):
    context_key = "roomtype_by_room_id"

    def batch_load(self, keys):
        def with_rooms(rooms):
            room_ids = {p.id for p in rooms}
            room_types_map = RoomType.objects.filter(
                rooms__in=room_ids
            ).in_bulk()
            return [room_types_map[room.room_type_id] for room in rooms]

        return RoomByIdLoader(self.context).load_many(keys).then(with_rooms)


class RoomTypeByVariantIdLoader(DataLoader):
    context_key = "roomtype_by_variant_id"

    def batch_load(self, keys):
        def with_variants(variants):
            room_ids = [v.room_id for v in variants]
            return RoomTypeByRoomIdLoader(self.context).load_many(room_ids)

        return (
            RoomVariantByIdLoader(self.context).load_many(keys).then(with_variants)
        )


class CollectionChannelListingByIdLoader(DataLoader):
    context_key = "collectionchannelisting_by_id"

    def batch_load(self, keys):
        collections = CollectionChannelListing.objects.in_bulk(keys)
        return [collections.get(key) for key in keys]


class CollectionChannelListingByCollectionIdLoader(DataLoader):
    context_key = "collectionchannelisting_by_collection"

    def batch_load(self, keys):
        collections_channel_listings = CollectionChannelListing.objects.filter(
            collection_id__in=keys
        )
        collection_id_collection_channel_listings_map = defaultdict(list)
        for collection_channel_listing in collections_channel_listings:
            collection_id_collection_channel_listings_map[
                collection_channel_listing.collection_id
            ].append(collection_channel_listing)
        return [
            collection_id_collection_channel_listings_map.get(collection_id, [])
            for collection_id in keys
        ]


class CollectionChannelListingByCollectionIdAndChannelSlugLoader(DataLoader):
    context_key = "collectionchannelisting_by_collection_and_channel"

    def batch_load(self, keys):
        collection_ids = [key[0] for key in keys]
        channel_slugs = [key[1] for key in keys]
        collections_channel_listings = CollectionChannelListing.objects.filter(
            collection_id__in=collection_ids, channel__slug__in=channel_slugs
        ).annotate(channel_slug=F("channel__slug"))
        collections_channel_listings_by_collection_and_channel_map = {}
        for collections_channel_listing in collections_channel_listings:
            key = (
                collections_channel_listing.collection_id,
                collections_channel_listing.channel_slug,
            )
            collections_channel_listings_by_collection_and_channel_map[
                key
            ] = collections_channel_listing
        return [
            collections_channel_listings_by_collection_and_channel_map.get(key, None)
            for key in keys
        ]
