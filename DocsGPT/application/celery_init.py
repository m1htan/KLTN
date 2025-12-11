from celery import Celery
from celery.signals import setup_logging

from application.core.settings import settings


def make_celery(app_name=__name__):
    celery = Celery(
        app_name,
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            "application.api.user.auto_ingest",
            "application.api.user.tasks",
        ],
    )
    celery.conf.update(settings)
    return celery


@setup_logging.connect
def config_loggers(*args, **kwargs):
    from application.core.logging_config import setup_logging

    setup_logging()


celery = make_celery()
