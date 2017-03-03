# -*- encoding: utf-8 -*-

import logging

import werkzeug.exceptions as wz_exceptions
from pillar.api.utils.authorization import user_matches_roles

from flamenco import current_flamenco, ROLES_REQUIRED_TO_VIEW_ITEMS

log = logging.getLogger(__name__)


def before_inserting_jobs(jobs):
    from flamenco import job_compilers, exceptions

    for job in jobs:
        try:
            job_compilers.validate_job(job)
        except exceptions.JobSettingError as ex:
            # We generally only submit one job at a time anyway.
            raise wz_exceptions.BadRequest('Invalid job: %s' % ex)


def after_inserting_jobs(jobs):
    from flamenco import job_compilers

    for job in jobs:
        # Prepare storage dir for the job files?
        # Generate tasks
        log.info('Generating tasks for job {}'.format(job['_id']))
        job_compilers.compile_job(job)


def check_job_permission_fetch(job_doc):

    if current_flamenco.current_user_is_flamenco_admin():
        return

    if not current_flamenco.manager_manager.user_is_manager():
        # Subscribers can read Flamenco jobs.
        if user_matches_roles(ROLES_REQUIRED_TO_VIEW_ITEMS):
            return
        raise wz_exceptions.Forbidden()

    mngr_doc_id = job_doc.get('manager')
    if not current_flamenco.manager_manager.user_manages(mngr_doc_id=mngr_doc_id):
        raise wz_exceptions.Forbidden()


def check_job_permission_fetch_resource(response):
    from functools import lru_cache

    if current_flamenco.current_user_is_flamenco_admin():
        return

    if not current_flamenco.manager_manager.user_is_manager():
        # Subscribers can read Flamenco jobs.
        if user_matches_roles(ROLES_REQUIRED_TO_VIEW_ITEMS):
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


def check_job_permissions_modify(job_doc, original_doc=None):
    """For now, only admins are allowed to create, edit, and delete jobs."""

    if not current_flamenco.current_user_is_flamenco_admin():
        raise wz_exceptions.Forbidden()

    # FIXME: check user access to the project.

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


def setup_app(app):
    app.on_insert_flamenco_jobs += before_inserting_jobs
    app.on_inserted_flamenco_jobs += after_inserting_jobs
    app.on_fetched_item_flamenco_jobs += check_job_permission_fetch
    app.on_fetched_resource_flamenco_jobs += check_job_permission_fetch_resource

    app.on_insert_flamenco_jobs += check_job_permissions_modify
    app.on_update_flamenco_jobs += check_job_permissions_modify
    app.on_replace_flamenco_jobs += check_job_permissions_modify
    app.on_delete_flamenco_jobs += check_job_permissions_modify
