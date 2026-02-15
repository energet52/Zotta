"""Celery task definitions for async processing."""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "zotta",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Port_of_Spain",
    enable_utc=True,
)

# Periodic beat schedule
celery_app.conf.beat_schedule = {
    "check-overdue-daily": {
        "task": "app.tasks.collection_reminders.check_overdue_and_notify",
        "schedule": crontab(hour=9, minute=0),  # 9 AM Trinidad time
    },
}

# Import tasks so they get registered
from app.tasks.decision_tasks import *  # noqa
from app.tasks.collection_reminders import *  # noqa