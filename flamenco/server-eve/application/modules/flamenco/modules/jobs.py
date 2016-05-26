import logging

log = logging.getLogger(__name__)


def after_inserting_jobs(items):
    for item in items:
        # Generate tasks
        log.debug('Generating tasks for job {}'.format(item['_id']))


def setup_app(app):
    # Permission hooks
    app.on_inserted_jobs += after_inserting_jobs

