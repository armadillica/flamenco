"""Task patching support."""

import logging

import bson
from flask import Blueprint, redirect, url_for
import werkzeug.exceptions as wz_exceptions

from pillar.api.projects.utils import get_project_url
from pillar.api.utils import authorization
from pillar.api import patch_handler

from . import LOG_UPLOAD_REQUESTABLE_TASK_STATES

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
        task = tasks_coll.find_one({'_id': task_id},
                                   projection={'job': 1, 'manager': 1, 'status': 1})

        if not current_flamenco.manager_manager.user_may_use(mngr_doc_id=task['manager']):
            log.warning('patch_set_task_status(%s, %r): User %s is not allowed to use manager %s!',
                        task_id, patch, current_user_id(), task['manager'])
            raise wz_exceptions.Forbidden()

        new_status = patch['status']
        try:
            current_flamenco.task_manager.api_set_task_status(task, new_status)
        except ValueError:
            raise wz_exceptions.UnprocessableEntity('Invalid status')

    @authorization.require_login()
    def patch_requeue(self, task_id: bson.ObjectId, patch: dict):
        """Re-queue a task and its successors."""

        from flamenco import current_flamenco
        from pillar.api.utils.authentication import current_user_id

        tasks_coll = current_flamenco.db('tasks')
        task = tasks_coll.find_one({'_id': task_id}, projection={'job': 1, 'manager': 1})

        if not current_flamenco.manager_manager.user_may_use(mngr_doc_id=task['manager']):
            log.warning('patch_set_task_status(%s, %r): User %s is not allowed to use manager %s!',
                        task_id, patch, current_user_id(), task['manager'])
            raise wz_exceptions.Forbidden()

        current_flamenco.task_manager.api_requeue_task_and_successors(task_id)

        # Also inspect other tasks of the same job, and possibly update the job status as well.
        current_flamenco.job_manager.update_job_after_task_status_change(
            task['job'], task_id, 'queued')

    @authorization.require_login()
    def patch_request_task_log_file(self, task_id: bson.ObjectId, patch: dict):
        """Queue a request to the Manager to upload this task's log file."""

        from flamenco import current_flamenco
        from pillar.api.utils.authentication import current_user_id

        tasks_coll = current_flamenco.db('tasks')
        task = tasks_coll.find_one(
            {'_id': task_id},
            projection={'job': 1, 'manager': 1, 'log_file': 1, 'project': 1, 'status': 1})

        if not current_flamenco.manager_manager.user_may_use(mngr_doc_id=task['manager']):
            log.warning('request_task_log_file(%s, %r): User %s is not allowed to use manager %s!',
                        task_id, patch, current_user_id(), task['manager'])
            raise wz_exceptions.Forbidden()

        status = task['status']
        if status not in LOG_UPLOAD_REQUESTABLE_TASK_STATES:
            ok = ', '.join(LOG_UPLOAD_REQUESTABLE_TASK_STATES)
            raise wz_exceptions.BadRequest(
                f'Log file not requestable while task is in status {status}, must be in {ok}')

        # Check that the log file hasn't arrived yet (this may not be the
        # first request for this task).
        force_rerequest = patch.get('force_rerequest', False)
        if task.get('log_file') and not force_rerequest:
            url = url_for('flamenco.tasks.perproject.download_task_log_file',
                          project_url=get_project_url(task['project']),
                          task_id=task_id)
            # Using 409 Conflict because a 303 See Other (which would be more
            # appropriate) cannot be intercepted by some AJAX calls.
            return redirect(url, code=409)

        current_flamenco.manager_manager.queue_task_log_request(
            task['manager'], task['job'], task_id)


def setup_app(app):
    TaskPatchHandler(blueprint)
    app.register_api_blueprint(blueprint, url_prefix='/flamenco/tasks')
