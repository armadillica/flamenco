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

    @authorization.require_login(require_roles={'flamenco-admin'})
    def patch_set_job_status(self, job_id: bson.ObjectId, patch: dict):
        """Updates a job's status in the database."""

        from flamenco import current_flamenco
        from pillar.api.utils.authentication import current_user_id

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
