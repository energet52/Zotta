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
    "execute-sequence-steps": {
        "task": "app.tasks.collection_reminders.execute_sequence_steps",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
    # ── Queue Management ─────────────────────────────────
    "sync-queue-entries": {
        "task": "app.tasks.queue_tasks.sync_queue_entries",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "recalculate-priorities": {
        "task": "app.tasks.queue_tasks.recalculate_priorities",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "check-sla": {
        "task": "app.tasks.queue_tasks.check_sla",
        "schedule": crontab(minute="*/10"),  # Every 10 minutes
    },
    "detect-stuck": {
        "task": "app.tasks.queue_tasks.detect_stuck",
        "schedule": crontab(minute=0, hour="*/2"),  # Every 2 hours
    },
    "auto-assign-queue": {
        "task": "app.tasks.queue_tasks.auto_assign",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "auto-expire-queue": {
        "task": "app.tasks.queue_tasks.auto_expire",
        "schedule": crontab(hour=23, minute=0),  # 11 PM daily
    },
    # Pre-Approval lifecycle
    "expire-pre-approvals": {
        "task": "app.tasks.pre_approval_tasks.expire_pre_approvals",
        "schedule": crontab(hour=1, minute=0),  # 1 AM daily
    },
    "purge-old-pre-approvals": {
        "task": "app.tasks.pre_approval_tasks.purge_old_pre_approvals",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Weekly Sunday 2 AM
    },
}

# Import tasks so they get registered
from app.tasks.decision_tasks import *  # noqa
from app.tasks.collection_reminders import *  # noqa
from app.tasks.queue_tasks import *  # noqa
from app.tasks.pre_approval_tasks import *  # noqa