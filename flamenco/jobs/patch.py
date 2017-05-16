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

    @authorization.require_login(require_roles={'subscriber', 'demo', 'flamenco-admin'})
    def patch_set_job_status(self, job_id: bson.ObjectId, patch: dict):
        """Updates a job's status in the database."""

        from flamenco import current_flamenco
        from pillar.api.utils.authentication import current_user_id

        # TODO: possibly store job and project into flask.g to reduce the nr of Mongo queries.
        job = current_flamenco.db('jobs').find_one({'_id': job_id}, {'project': 1})
        auth = current_flamenco.auth
        if not auth.current_user_may(job['project'], auth.Actions.USE):
            log.info('User %s wants to PATCH job %s, but has no right to use Flamenco on project %s',
                     current_user_id(), job_id, job['project'])
            raise wz_exceptions.Forbidden('Denied Flamenco use on this project')

        new_status = patch['status']

        log.info('User %s uses PATCH to set job %s status to "%s"',
                 current_user_id(), job_id, new_status)
        try:
            current_flamenco.job_manager.api_set_job_status(job_id, new_status)
        except ValueError:
            raise wz_exceptions.UnprocessableEntity(f'Status {new_status} is invalid')


def setup_app(app):
    JobPatchHandler(patch_api_blueprint)
    app.register_api_blueprint(patch_api_blueprint, url_prefix='/flamenco/jobs')
