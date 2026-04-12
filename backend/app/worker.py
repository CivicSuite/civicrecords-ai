from celery import Celery

from app.config import settings

celery_app = Celery(
    "civicrecords",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="civicrecords.health")
def health_check():
    """Simple health check task."""
    return {"status": "ok"}
