from ..celeryconf import app
from ..core.utils import create_thumbnails
from .models import Hotel


@app.task
def create_hotel_cover_image_thumbnails(hotel_id):
    """Create thumbnails for user avatar."""
    create_thumbnails(
        pk=hotel_id, model=Hotel, size_set="hotel_cover_images", image_attr="cover_image"
    )
