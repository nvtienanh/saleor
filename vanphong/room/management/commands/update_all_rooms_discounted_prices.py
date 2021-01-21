import logging

from django.core.management.base import BaseCommand
from tqdm import tqdm

from ....discount.utils import fetch_active_discounts
from ...models import Room
from ...utils.variant_prices import update_room_discounted_price

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Recalculates the discounted prices for rooms in all channels."

    def handle(self, *args, **options):
        self.stdout.write('Updating "discounted_price" field of all the rooms.')
        # Fetching the discounts just once and reusing them
        discounts = fetch_active_discounts()
        # Run the update on all the rooms with "progress bar" (tqdm)
        qs = Room.objects.all()
        for room in tqdm(qs.iterator(), total=qs.count()):
            update_room_discounted_price(room, discounts=discounts)
