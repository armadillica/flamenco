# -*- encoding: utf-8 -*-

import logging

import werkzeug.exceptions as wz_exceptions
from pillar.auth import current_user

import flamenco.eve_hooks
from flamenco import current_flamenco

log = logging.getLogger(__name__)


def before_inserting_jobs(jobs):
    from flamenco import job_compilers, exceptions

    for job in jobs:
        # Jobs are forced to be 'under construction' when they are created.
        # This is set to 'queued' when job compilation is finished.
        job['status'] = 'under-construction'

        try:
            job_compilers.validate_job(job)
        except exceptions.JobSettingError as ex:
            # We generally only submit one job at a time anyway.
            raise wz_exceptions.BadRequest('Invalid job: %s' % ex)


def after_inserting_jobs(jobs):
    from flamenco import job_compilers, current_flamenco

    for job in jobs:
        job_id = job['_id']
        # Prepare storage dir for the job files?
        # Generate tasks
        log.info(f'Generating tasks for job {job_id}')

        try:
            job_compilers.compile_job(job)
        except Exception:
            log.exception('Compiling job %s failed', job_id)
            job['status'] = 'construction-failed'
            current_flamenco.job_manager.api_set_job_status(job_id, job['status'])


def check_job_permission_fetch(job_doc):
    flamenco.eve_hooks.check_permission_fetch(job_doc, doc_name='job')


def check_job_permission_fetch_resource(response):
    from functools import lru_cache

    if current_flamenco.auth.current_user_is_flamenco_admin():
        return

    if not current_flamenco.manager_manager.user_is_manager():
        # Subscribers can read Flamenco jobs.
        if current_user.has_cap('flamenco-view'):
            return
        raise wz_exceptions.Forbidden()

    @lru_cache(32)
    def user_managers(mngr_doc_id):
        return current_flamenco.manager_manager.user_manages(mngr_doc_id=mngr_doc_id)

    items = response['_items']
    to_remove = []
    for idx, job_doc in enumerate(items):
        if not user_managers(job_doc.get('manager')):
            to_remove.append(idx)

    for idx in reversed(to_remove):
        del items[idx]

    response['_meta']['total'] -= len(items)


def check_jobs_permissions_modify(job_docs):
    """Checks whether the current user is allowed to use Flamenco on this project."""

    for job in job_docs:
        check_job_permissions_modify(job)


def check_job_permissions_modify(job_doc, original_doc=None):
    """Checks whether the current user is allowed to use Flamenco on this project."""

    flauth = current_flamenco.auth
    if not flauth.current_user_may(flauth.Actions.USE, job_doc.get('project')):
        from pillar.api.utils.authentication import current_user_id
        from flask import request

        log.warning('Denying user %s %s of job %s',
                    current_user_id(), request.method, job_doc.get('_id'))
        raise wz_exceptions.Forbidden()

    handle_job_status_update(job_doc, original_doc)


def handle_job_status_update(job_doc, original_doc):
    """Calls upon the JobManager to handle a job status update, if there is any."""

    if original_doc is None:
        return

    job_id = job_doc.get('_id')
    if not job_id:
        log.warning('handle_job_status_update: No _id in new job document, rejecting')
        raise wz_exceptions.UnprocessableEntity('missing _id')

    try:
        old_status = original_doc['status']
    except KeyError:
        log.info('handle_job_status_update: No status in old job document %s, ignoring', job_id)
        return

    try:
        new_status = job_doc['status']
    except KeyError:
        log.warning('handle_job_status_update: No status in new job document %s, rejecting', job_id)
        raise wz_exceptions.UnprocessableEntity('missing status field')

    if old_status == new_status:
        # No change, so nothing to handle.
        return

    from flamenco import current_flamenco
    current_flamenco.job_manager.handle_job_status_change(job_id, old_status, new_status)


def reject_resource_deletion(*args):
    log.warning("Rejecting DELETE on jobs resource")
    raise wz_exceptions.Forbidden()


def setup_app(app):
    app.on_insert_flamenco_jobs += before_inserting_jobs
    app.on_inserted_flamenco_jobs += after_inserting_jobs
    app.on_fetched_item_flamenco_jobs += check_job_permission_fetch
    app.on_fetched_resource_flamenco_jobs += check_job_permission_fetch_resource

    app.on_insert_flamenco_jobs += check_jobs_permissions_modify
    app.on_update_flamenco_jobs += check_job_permissions_modify
    app.on_replace_flamenco_jobs += check_job_permissions_modify
    app.on_delete_item_flamenco_jobs += check_job_permissions_modify
    app.on_delete_resource_flamenco_jobs += reject_resource_deletion
