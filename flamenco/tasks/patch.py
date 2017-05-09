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

    @authorization.require_login()
    def patch_set_task_status(self, task_id: bson.ObjectId, patch: dict):
        """Updates a task's status in the database."""

        from flamenco import current_flamenco
        from pillar.api.utils.authentication import current_user_id

        tasks_coll = current_flamenco.db('tasks')
        task = tasks_coll.find_one({'_id': task_id}, projection={'job': 1, 'manager': 1})

        if not current_flamenco.manager_manager.user_may_use(mngr_doc_id=task['manager']):
            log.warning('patch_set_task_status(%s, %r): User %s is not allowed to use manager %s!',
                        task_id, patch, current_user_id(), task['manager'])
            raise wz_exceptions.Forbidden()

        new_status = patch['status']
        try:
            current_flamenco.update_status('tasks', task_id, new_status)
        except ValueError:
            raise wz_exceptions.UnprocessableEntity('Invalid status')

        # also inspect other tasks of the same job, and possibly update the job status as well.
        current_flamenco.job_manager.update_job_after_task_status_change(task['job'],
                                                                         task_id,
                                                                         new_status)


def setup_app(app):
    TaskPatchHandler(blueprint)
    app.register_api_blueprint(blueprint, url_prefix='/flamenco/tasks')
