"""
Celery application configuration.
"""

from celery import Celery

from app.config import settings

# Create Celery app
celery_app = Celery(
    "rizzler",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.document_processor"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Result backend
    result_expires=3600,  # 1 hour

    # Task routing
    task_routes={
        "app.workers.document_processor.*": {"queue": "documents"},
    },

    # Rate limiting
    task_annotations={
        "app.workers.document_processor.process_document": {
            "rate_limit": "10/m",  # 10 per minute
        },
    },
)

