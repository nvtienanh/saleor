import os
import re
from datetime import datetime

import pytz
from django.conf import settings
from django.template.loader import get_template
from weasyprint import HTML

from ...invoice.models import Invoice

MAX_ROOMS_WITH_TABLE = 3
MAX_ROOMS_WITHOUT_TABLE = 4
MAX_ROOMS_PER_PAGE = 13


def make_full_invoice_number(number=None, month=None, year=None):
    now = datetime.now()
    current_month = int(now.strftime("%m"))
    current_year = int(now.strftime("%Y"))
    month_and_year = now.strftime("%m/%Y")

    if month == current_month and year == current_year:
        new_number = (number or 0) + 1
        return f"{new_number}/{month_and_year}"
    return f"1/{month_and_year}"


def parse_invoice_dates(invoice):
    match = re.match(r"^(\d+)\/(\d+)\/(\d+)", invoice.number)
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def generate_invoice_number():
    last_invoice = Invoice.objects.filter(number__isnull=False).last()
    if not last_invoice or not last_invoice.number:
        return make_full_invoice_number()

    try:
        number, month, year = parse_invoice_dates(last_invoice)
        return make_full_invoice_number(number, month, year)
    except (IndexError, ValueError, AttributeError):
        return make_full_invoice_number()


def chunk_rooms(rooms, room_limit):
    """Split rooms to list of chunks.

    Each chunk represents rooms per page, room_limit defines chunk size.
    """
    chunks = []
    for i in range(0, len(rooms), room_limit):
        limit = i + room_limit
        chunks.append(rooms[i:limit])
    return chunks


def get_room_limit_first_page(rooms):
    if len(rooms) < MAX_ROOMS_WITHOUT_TABLE:
        return MAX_ROOMS_WITH_TABLE

    return MAX_ROOMS_WITHOUT_TABLE


def generate_invoice_pdf(invoice):
    font_path = os.path.join(
        settings.PROJECT_ROOT, "templates", "invoices", "inter.ttf"
    )

    all_rooms = invoice.order.lines.all()

    room_limit_first_page = get_room_limit_first_page(all_rooms)

    rooms_first_page = all_rooms[:room_limit_first_page]
    rest_of_rooms = chunk_rooms(
        all_rooms[room_limit_first_page:], MAX_ROOMS_PER_PAGE
    )
    creation_date = datetime.now(tz=pytz.utc)
    rendered_template = get_template("invoices/invoice.html").render(
        {
            "invoice": invoice,
            "creation_date": creation_date.strftime("%d %b %Y"),
            "order": invoice.order,
            "font_path": f"file://{font_path}",
            "rooms_first_page": rooms_first_page,
            "rest_of_rooms": rest_of_rooms,
        }
    )
    return HTML(string=rendered_template).write_pdf(), creation_date
