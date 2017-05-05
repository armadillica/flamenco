"""Task patching support."""

import logging

import bson
from flask import Blueprint
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils import authorization
from pillar.api import patch_handler

log = logging.getLogger(__name__)
blueprint = Blueprint('flamenco.tasks.patch', __name__)


class TaskPatchHandler(patch_handler.AbstractPatchHandler):
    item_name = 'task'

    @authorization.require_login(require_roles={'flamenco-admin'})
    def patch_set_task_status(self, task_id: bson.ObjectId, patch: dict):
        """Updates a task's status in the database."""

        from flamenco import current_flamenco

        new_status = patch['status']

        # FIXME Sybren: add permission check.

        try:
            current_flamenco.update_status('tasks', task_id, new_status)
        except ValueError:
            raise wz_exceptions.UnprocessableEntity('Invalid status')

        # also inspect other tasks of the same job, and possibly update the job status as well.
        tasks_coll = current_flamenco.db('tasks')
        task_job = tasks_coll.find_one({'_id': task_id}, projection={'job': 1})

        current_flamenco.job_manager.update_job_after_task_status_change(task_job['job'],
                                                                         task_id,
                                                                         new_status)


def setup_app(app):
    TaskPatchHandler(blueprint)
    app.register_api_blueprint(blueprint, url_prefix='/flamenco/tasks')
