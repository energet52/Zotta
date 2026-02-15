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
    "sync-collection-cases": {
        "task": "app.tasks.collection_reminders.sync_cases",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
    },
    "check-ptp-daily": {
        "task": "app.tasks.collection_reminders.check_ptps",
        "schedule": crontab(hour=8, minute=30),  # 8:30 AM daily
    },
    "daily-collections-snapshot": {
        "task": "app.tasks.collection_reminders.daily_snapshot",
        "schedule": crontab(hour=23, minute=55),  # 11:55 PM daily
    },
}

# Import tasks so they get registered
from app.tasks.decision_tasks import *  # noqa
from app.tasks.collection_reminders import *  # noqa