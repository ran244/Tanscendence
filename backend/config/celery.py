from celery import Celery
from celery.schedules import crontab

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("mystery_auctions")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    from django.conf import settings

    sender.add_periodic_task(
        settings.CELERY_BEAT_SCHEDULE["auction-ticks"]["schedule"],
        settings.CELERY_BEAT_SCHEDULE["auction-ticks"]["task"],
        name="auction-ticks",
    )