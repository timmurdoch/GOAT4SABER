from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "ausgis",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.analysis_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Australia/Melbourne",
    enable_utc=True,
    task_track_started=True,
)
