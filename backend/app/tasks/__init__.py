"""Celery task definitions for async processing."""

from celery import Celery

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

# Import tasks so they get registered
from app.tasks.decision_tasks import *  # noqa
