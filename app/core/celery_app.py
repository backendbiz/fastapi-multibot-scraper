from celery import Celery
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from app.core.config import settings
import os

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            CeleryIntegration(),
        ],
        environment=settings.ENVIRONMENT,
        release=f"{settings.PROJECT_NAME}@{settings.VERSION}",
    )

celery_app = Celery("worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.task_routes = {
    "app.worker.tasks.*": "main-queue"
}

# Optional configuration, see the application user guide.
celery_app.conf.update(
    result_expires=3600,
)
