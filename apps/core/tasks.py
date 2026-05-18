from celery import shared_task


@shared_task
def ping() -> str:
    """Health-check task for Celery worker."""
    return 'pong'
