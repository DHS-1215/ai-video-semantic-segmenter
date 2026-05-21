from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "video_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_default_queue="video",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
)
