"""Clear the database preserving shop's configuration.

This command clears the database from data such as orders, rooms or customer
accounts. It doesn't remove shop's configuration, such as: staff accounts, service
accounts, plugin configurations, site settings or navigation menus.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from ....account.models import User
from ....attribute.models import Attribute
from ....checkout.models import Checkout
from ....discount.models import Sale, Voucher
from ....giftcard.models import GiftCard
from ....order.models import Order
from ....page.models import Page
from ....payment.models import Payment, Transaction
from ....room.models import Category, Collection, Room, RoomType
from ....shipping.models import ShippingMethod, ShippingZone
from ....hotel.models import Hotel
from ....webhook.models import Webhook


class Command(BaseCommand):
    help = "Removes data from the database preserving shop configuration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-staff",
            action="store_true",
            help="Delete staff user accounts (doesn't delete superuser accounts).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allows running the cleardb command in DEBUG=False mode.",
        )

    def handle(self, **options):
        force = options.get("force", False)
        if not settings.DEBUG and not force:
            raise CommandError("Cannot clear the database in DEBUG=False mode.")

        Checkout.objects.all().delete()
        self.stdout.write("Removed checkouts")

        Transaction.objects.all().delete()
        self.stdout.write("Removed transactions")

        Payment.objects.all().delete()
        self.stdout.write("Removed payments")

        Order.objects.all().delete()
        self.stdout.write("Removed orders")

        Room.objects.all().delete()
        self.stdout.write("Removed rooms")

        RoomType.objects.all().delete()
        self.stdout.write("Removed room types")

        Attribute.objects.all().delete()
        self.stdout.write("Removed attributes")

        Category.objects.all().delete()
        self.stdout.write("Removed categories")

        Collection.objects.all().delete()
        self.stdout.write("Removed collections")

        Sale.objects.all().delete()
        self.stdout.write("Removed sales")

        ShippingMethod.objects.all().delete()
        self.stdout.write("Removed shipping methods")

        ShippingZone.objects.all().delete()
        self.stdout.write("Removed shipping zones")

        Voucher.objects.all().delete()
        self.stdout.write("Removed vouchers")

        GiftCard.objects.all().delete()
        self.stdout.write("Removed gift cards")

        self.stdout.write("Removed hotels")
        Hotel.objects.all().delete()

        Page.objects.all().delete()
        self.stdout.write("Removed pages")

        Webhook.objects.all().delete()
        self.stdout.write("Removed webhooks")

        # Delete all users except for staff members.
        staff = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))
        User.objects.exclude(pk__in=staff).delete()
        self.stdout.write("Removed customers")

        should_delete_staff = options.get("delete_staff")
        if should_delete_staff:
            staff = staff.exclude(is_superuser=True)
            staff.delete()
            self.stdout.write("Removed staff users")

        # Remove addresses of staff members. Used to clear saved addresses of staff
        # accounts used on demo for testing checkout.
        for user in staff:
            user.addresses.all().delete()
        self.stdout.write("Removed staff addresses")
