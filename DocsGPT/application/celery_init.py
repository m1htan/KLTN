from celery import Celery
from application.core.settings import settings
from celery.signals import setup_logging


def make_celery(app_name=__name__):
    celery = Celery(
        app_name,
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )
    import application.api.user.auto_ingest
    celery.conf.update(settings)
    return celery


@setup_logging.connect
def config_loggers(*args, **kwargs):
    from application.core.logging_config import setup_logging

    setup_logging()

import application.api.user.auto_ingest

celery = make_celery()

import application.api.user.auto_ingest
