"""Job patching support."""

import logging

import bson
from flask import Blueprint
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils.authentication import current_user_id, current_user
from pillar.api.utils import authorization, jsonify
from pillar.api import patch_handler

from flamenco import current_flamenco
from . import rna_overrides as rna_overrides_mod


log = logging.getLogger(__name__)
patch_api_blueprint = Blueprint('flamenco.jobs.patch', __name__)


class JobPatchHandler(patch_handler.AbstractPatchHandler):
    item_name = 'job'

    @authorization.require_login(require_cap='flamenco-use')
    def patch_set_job_status(self, job_id: bson.ObjectId, patch: dict):
        """Updates a job's status in the database."""
        self.assert_job_access(job_id)

        new_status = patch['status']

        user = current_user()
        log.info('User %s uses PATCH to set job %s status to "%s"',
                 user.user_id, job_id, new_status)
        try:
            current_flamenco.job_manager.api_set_job_status(
                job_id, new_status,
                reason=f'Set to {new_status} by {user.full_name} (@{user.username})')
        except ValueError as ex:
            log.debug('api_set_job_status(%s, %r) raised %s', job_id, new_status, ex)
            raise wz_exceptions.UnprocessableEntity(f'Status {new_status} is invalid')

    @authorization.require_login(require_cap='flamenco-use')
    def patch_set_job_priority(self, job_id: bson.ObjectId, patch: dict):
        """Updates a job's priority in the database."""
        self.assert_job_access(job_id)

        new_prio = patch['priority']
        if not isinstance(new_prio, int):
            log.debug('patch_set_job_priority(%s): invalid prio %r received', job_id, new_prio)
            raise wz_exceptions.UnprocessableEntity(f'Priority {new_prio} should be an integer')

        log.info('User %s uses PATCH to set job %s priority to %d',
                 current_user_id(), job_id, new_prio)
        current_flamenco.job_manager.api_set_job_priority(job_id, new_prio)

    @authorization.require_login(require_cap='flamenco-use')
    def patch_archive_job(self, job_id: bson.ObjectId, patch: dict):
        """Archives the given job in a background task."""
        job = self.assert_job_access(job_id)

        log.info('User %s uses PATCH to start archival of job %s', current_user_id(), job_id)
        current_flamenco.job_manager.archive_job(job)

    @authorization.require_login(require_cap='flamenco-use')
    def patch_requeue_failed_tasks(self, job_id: bson.ObjectId, patch: dict):
        """Re-queue all failed tasks in this job."""
        self.assert_job_access(job_id)

        log.info('User %s uses PATCH to requeue failed tasks of job %s', current_user_id(), job_id)
        current_flamenco.task_manager.api_set_task_status_for_job(
            job_id, from_status='failed', to_status='queued')

    @authorization.require_login(require_cap='flamenco-use')
    def patch_rna_overrides(self, job_id: bson.ObjectId, patch: dict):
        """Update the RNA overrides of this render job, and re-queue dependent tasks.

        Note that once a job has RNA overrides, the RNA overrides task cannot
        be deleted. If such task deletion were possible, it would still not
        delete the RNA override file and effectively keep the old overrides in
        place. Having an empty overrides file is better.
        """
        self.assert_job_access(job_id)

        rna_overrides = patch.get('rna_overrides') or []
        if not all(isinstance(override, str) for override in rna_overrides):
            log.info('User %s wants to PATCH job %s to set RNA overrides, but not all '
                     'overrides are strings', current_user_id(), job_id)
            raise wz_exceptions.BadRequest(f'"rna_overrides" should be a list of strings,'
                                           f' not {rna_overrides!r}')

        result = rna_overrides_mod.validate_rna_overrides(rna_overrides)
        if result:
            msg, line_num = result
            log.info('User %s tries PATCH to update RNA overrides of job %s but has '
                     'error %r in override %d',
                     current_user_id(), job_id, msg, line_num)

            return jsonify({
                'validation_error': {
                    'message': msg,
                    'line_num': line_num,
                }
            }, status=422)

        log.info('User %s uses PATCH to update RNA overrides of job %s to %d overrides',
                 current_user_id(), job_id, len(rna_overrides))
        current_flamenco.job_manager.api_update_rna_overrides(job_id, rna_overrides)

    def assert_job_access(self, job_id: bson.ObjectId) -> dict:
        # TODO: possibly store job and project into flask.g to reduce the nr of Mongo queries.
        job = current_flamenco.db('jobs').find_one({'_id': job_id},
                                                   {'project': 1,
                                                    'status': 1})
        auth = current_flamenco.auth

        if not auth.current_user_may(auth.Actions.USE, job['project']):
            log.info(
                'User %s wants to PATCH job %s, but has no right to use Flamenco on project %s',
                current_user_id(), job_id, job['project'])
            raise wz_exceptions.Forbidden('Denied Flamenco use on this project')

        return job


def setup_app(app):
    JobPatchHandler(patch_api_blueprint)
    app.register_api_blueprint(patch_api_blueprint, url_prefix='/flamenco/jobs')
