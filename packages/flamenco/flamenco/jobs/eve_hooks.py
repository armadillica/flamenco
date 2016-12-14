# -*- encoding: utf-8 -*-

import logging

from pillar.api.utils.authorization import check_permissions

log = logging.getLogger(__name__)


def after_inserting_jobs(jobs):
    from flamenco import job_compilers

    for job in jobs:
        # Prepare storage dir for the job files?
        # Generate tasks
        log.debug('Generating tasks for job {}'.format(job['_id']))
        job_compilers.compile_job(job)


def before_returning_job_permissions(response):
    # Run validation process, since GET on nodes entry point is public
    check_permissions('flamenco.jobs', response, 'GET',
                      append_allowed_methods=True)


def setup_app(app):
    app.on_inserted_jobs = after_inserting_jobs
    app.on_fetched_item_jobs += before_returning_job_permissions
