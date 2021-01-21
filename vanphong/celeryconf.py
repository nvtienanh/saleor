import os

from celery import Celery
from django.conf import settings

from .plugins import discover_plugins_modules

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vanphong.settings")

app = Celery("vanphong")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.autodiscover_tasks(lambda: discover_plugins_modules(settings.PLUGINS))
