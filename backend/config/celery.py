import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
app = Celery(
    "config",
    broker=settings.CELERY_BROKER_URL,
    worker_cancel_long_running_tasks_on_connection_loss=True,
)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery_bootstrap-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# --- Load task modules from all registered Django app configs. ---------------------------------------------------- #
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# --- This will make sure the app is always imported when Django starts so that shared_task will use this app. --- #
__all__ = ("app", settings.CELERY_RETRY_DELAY, settings.CELERY_RETRY_MAX_TIMES)