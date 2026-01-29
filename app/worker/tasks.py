from celery import shared_task
import time
import logging

logger = logging.getLogger(__name__)

@shared_task(name="app.worker.tasks.test_celery")
def test_celery(word: str) -> str:
    logger.info(f"Test task received: {word}")
    time.sleep(1)
    return f"test task return {word}"
