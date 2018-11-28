"""Job patching support."""

import logging

import bson
from flask import Blueprint
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils import authorization
from pillar.api import patch_handler

log = logging.getLogger(__name__)
patch_api_blueprint = Blueprint('flamenco.jobs.patch', __name__)


class JobPatchHandler(patch_handler.AbstractPatchHandler):
    item_name = 'job'

    @authorization.require_login(require_cap='flamenco-use')
    def patch_set_job_status(self, job_id: bson.ObjectId, patch: dict):
        """Updates a job's status in the database."""

        from flamenco import current_flamenco
        from pillar.api.utils.authentication import current_user_id

        self.assert_job_access(job_id)

        new_status = patch['status']

        log.info('User %s uses PATCH to set job %s status to "%s"',
                 current_user_id(), job_id, new_status)
        try:
            current_flamenco.job_manager.api_set_job_status(job_id, new_status)
        except ValueError as ex:
            log.debug('api_set_job_status(%s, %r) raised %s', job_id, new_status, ex)
            raise wz_exceptions.UnprocessableEntity(f'Status {new_status} is invalid')

    @authorization.require_login(require_cap='flamenco-use')
    def patch_set_job_priority(self, job_id: bson.ObjectId, patch: dict):
        """Updates a job's priority in the database."""

        from flamenco import current_flamenco
        from pillar.api.utils.authentication import current_user_id

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

        from flamenco import current_flamenco
        from pillar.api.utils.authentication import current_user_id

        job = self.assert_job_access(job_id)

        log.info('User %s uses PATCH to start archival of job %s', current_user_id(), job_id)
        current_flamenco.job_manager.archive_job(job)

    @authorization.require_login(require_cap='flamenco-use')
    def patch_requeue_failed_tasks(self, job_id: bson.ObjectId, patch: dict):
        """Re-queue all failed tasks in this job."""

        from flamenco import current_flamenco
        from pillar.api.utils.authentication import current_user_id

        self.assert_job_access(job_id)

        log.info('User %s uses PATCH to requeue failed tasks of job %s', current_user_id(), job_id)
        current_flamenco.task_manager.api_set_task_status_for_job(
            job_id, from_status='failed', to_status='queued')

    def assert_job_access(self, job_id: bson.ObjectId) -> dict:
        from flamenco import current_flamenco
        from pillar.api.utils.authentication import current_user_id

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
