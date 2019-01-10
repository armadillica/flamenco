import logging
from urllib.parse import urljoin

import bson
import flask_login
from flask import Blueprint, render_template, request, redirect, Response, url_for
import werkzeug.exceptions as wz_exceptions

from pillar import current_app
import pillar.flask_extra
from pillar.web.system_util import pillar_api
from pillar.web.utils import is_valid_id, last_page_index
from pillar.auth import current_user
import pillarsdk

from flamenco import current_flamenco
from flamenco.auth import Actions
from flamenco.managers.sdk import Manager
from flamenco.routes import flamenco_project_view
from flamenco.tasks.sdk import Task, TaskLog

from . import LOG_UPLOAD_REQUESTABLE_TASK_STATES

TASK_LOG_PAGE_SIZE = 10

# The task statuses that can be set from the web-interface.
ALLOWED_TASK_STATUSES_FROM_WEB = {'cancel-requested', 'queued'}

global_blueprint = Blueprint('flamenco.tasks', __name__,
                             url_prefix='/tasks')

perjob_blueprint = Blueprint('flamenco.tasks.perjob', __name__,
                             url_prefix='/<project_url>/jobs/<job_id>')
perproject_blueprint = Blueprint('flamenco.tasks.perproject', __name__,
                                 url_prefix='/<project_url>/tasks')
log = logging.getLogger(__name__)


@global_blueprint.route('/<task_id>')
def redirect_to_task(task_id):
    """Allows creation of task links without knowing the job or project ID."""
    api = pillar_api()

    task = Task.find(task_id, {'projection': {'project': 1}}, api=api)
    project = pillarsdk.Project.find(task['project'], {'projection': {'url': 1}}, api=api)

    # FIXME Sybren: add permission check.

    url = url_for('flamenco.jobs.perproject.for_project_with_task',
                  project_url=project['url'], task_id=task_id)
    return redirect(url, code=301)


@perproject_blueprint.route('/', endpoint='index')
@flamenco_project_view(action=Actions.VIEW)
def list_for_project(project, task_id=None):
    tasks = current_flamenco.task_manager.tasks_for_project(project['_id'])
    return render_template('flamenco/tasks/list_for_project.html',
                           tasks=tasks['_items'],
                           open_task_id=task_id,
                           project=project)


@perjob_blueprint.route('/tasks')
@flamenco_project_view(action=Actions.VIEW)
def list_for_job(project, job_id, task_id=None):
    page_idx = int(request.args.get('page', '1'))

    tasks = current_flamenco.task_manager.tasks_for_job(
        job_id, page=page_idx, max_results=40)

    return render_template('flamenco/tasks/list_for_job_embed.html',
                           job_id=job_id,
                           tasks=tasks['_items'],
                           open_task_id=task_id,
                           project=project,
                           task_count=tasks['_meta']['total'],
                           page_idx=page_idx,
                           page_count=last_page_index(tasks['_meta']),
                           )


@perproject_blueprint.route('/<task_id>')
@flask_login.login_required
@pillar.flask_extra.vary_xhr()
@flamenco_project_view(extension_props=True, action=Actions.VIEW)
def view_task(project, flamenco_props, task_id):
    api = pillar_api()

    if not request.is_xhr:
        # Render page that'll perform the XHR.
        from flamenco.jobs import routes as job_routes

        task = Task.find(task_id, {'projection': {'job': 1}}, api=api)
        return job_routes.for_project(project, job_id=task['job'], task_id=task_id)

    # Task list is public, task details are not.
    if not current_user.has_cap('flamenco-view'):
        raise wz_exceptions.Forbidden()

    task = Task.find(task_id, api=api)

    from . import REQUEABLE_TASK_STATES, CANCELABLE_TASK_STATES
    project_id = bson.ObjectId(project['_id'])

    write_access = current_flamenco.auth.current_user_may(Actions.USE, project_id)
    can_requeue_task = write_access and task['status'] in REQUEABLE_TASK_STATES
    can_requeue_successors = write_access and task['status'] in (REQUEABLE_TASK_STATES | {'queued'})
    can_cancel_task = write_access and task['status'] in CANCELABLE_TASK_STATES

    if write_access and task.log:
        # Having task.log means the Manager is using the current approach of sending
        # the log tail only. Not having it means the Manager is using the deprecated
        # approach of sending the entire log, thus it isn't upgraded to 2.2+ yet, and
        # thus it doesn't support the logfile endpoint yet.
        manager = Manager.find(task.manager, api=api)
        log_download_url = urljoin(manager.url, f'logfile/{task.job}/{task._id}')
    else:
        log_download_url = ''

    # can_... = is actually possible (but maybe should be forced).
    can_request_log_file = task['status'] in LOG_UPLOAD_REQUESTABLE_TASK_STATES
    # may_... = the regular 'request' button should be shown.
    may_request_log_file = False
    log_file_download_url = ''
    if write_access and task.log_file:
        # Having task.log_file means the same as above, and the Manager has sent us
        # the compressed log file.
        log_file_download_url = url_for(
            'flamenco.tasks.perproject.download_task_log_file',
            project_url=project['url'], task_id=task_id)
    elif log_download_url:
        # This means the Manager supports sending us the log file, but hasn't yet.
        may_request_log_file = can_request_log_file

    return render_template('flamenco/tasks/view_task_embed.html',
                           task=task,
                           project=project,
                           flamenco_props=flamenco_props.to_dict(),
                           flamenco_context=request.args.get('context'),
                           log_download_url=log_download_url,
                           can_view_log=write_access,
                           log_file_download_url=log_file_download_url,
                           can_request_log_file=can_request_log_file,
                           may_request_log_file=may_request_log_file,
                           can_requeue_task=can_requeue_task,
                           can_requeue_task_and_successors=can_requeue_successors,
                           can_cancel_task=can_cancel_task)


@perproject_blueprint.route('/<task_id>/set-status', methods=['POST'])
@flask_login.login_required
@flamenco_project_view(action=Actions.USE)
def set_task_status(project, task_id):
    new_status = request.form['status']
    if new_status not in ALLOWED_TASK_STATUSES_FROM_WEB:
        log.warning('User %s tried to set status of task %s to disallowed status "%s"; denied.',
                    current_user.objectid, task_id, new_status)
        raise wz_exceptions.UnprocessableEntity('Status "%s" not allowed' % new_status)

    log.info('User %s set status of task %s to "%s"', current_user.objectid, task_id, new_status)
    current_flamenco.task_manager.web_set_task_status(task_id, new_status)

    return '', 204


@perproject_blueprint.route('/<task_id>/log')
@flask_login.login_required
@flamenco_project_view(action=Actions.USE)
def view_task_log(project, task_id):
    """Shows a limited number of task log entries.

    Pass page=N (N≥1) to request further entries.
    """
    if not is_valid_id(task_id):
        raise wz_exceptions.UnprocessableEntity()

    page_idx = int(request.args.get('page', 1))
    api = pillar_api()
    try:
        logs = TaskLog.all({'where': {'task': task_id},
                            'page': page_idx,
                            'max_results': TASK_LOG_PAGE_SIZE},
                           api=api)
    except pillarsdk.ResourceNotFound:
        logs = {'_items': [],
                '_meta': {'total': 0,
                          'page': page_idx,
                          'max_results': TASK_LOG_PAGE_SIZE}}

    last_page_idx = last_page_index(logs['_meta'])
    has_next_page = page_idx < last_page_idx
    has_prev_page = page_idx > 1

    return render_template('flamenco/tasks/view_task_log_embed.html',
                           page_idx=page_idx,
                           logs=logs,
                           has_prev_page=has_prev_page,
                           has_next_page=has_next_page,
                           last_page_idx=last_page_idx,
                           project=project,
                           task_id=task_id)


@perproject_blueprint.route('/<task_id>/download-log')
@flask_login.login_required
@flamenco_project_view(action=Actions.USE)
def download_task_log(project, task_id):
    """Show the entire task log as text/plain.

    This endpoint is for obtaining the task log stored in MongoDB. This
    approach is deprecated in favour of having the Manager store & serve the
    logs and upload them to the Server on demand (see flamenco.managers.api).
    """

    if not is_valid_id(task_id):
        raise wz_exceptions.UnprocessableEntity()

    # Required because the stream_log() generator will run outside the app context.
    app = current_app.real_app
    api = pillar_api()

    def stream_log():
        page_idx = 1
        while True:
            with app.app_context():
                logs = TaskLog.all({'where': {'task': task_id},
                                    'page': page_idx,
                                    'max_results': TASK_LOG_PAGE_SIZE},
                                   api=api)

            for tasklog in logs['_items']:
                yield tasklog.log + '\n'

            if page_idx >= last_page_index(logs['_meta']):
                break

            page_idx += 1

    return Response(stream_log(), mimetype='text/plain')


@perproject_blueprint.route('/<task_id>.log.gz')
@flask_login.login_required
@flamenco_project_view(action=Actions.USE)
def download_task_log_file(project, task_id):
    """Redirect to the storage backend for the task log.

    This endpoint is for obtaining the task log sent to us by Flamenco Manager,
    and stored as a gzipped file in the storage backend. See the Manager API
    for the endpoint that actually accepts the log file from the Manager.
    """
    from pillar.web.utils import is_valid_id
    from .sdk import Task

    if not is_valid_id(task_id):
        raise wz_exceptions.UnprocessableEntity()

    api = pillar_api()
    task = Task.find(task_id, api=api)

    if not task.log_file:
        return wz_exceptions.NotFound(f'Task {task_id} has no attached log file')

    blob = current_flamenco.task_manager.logfile_blob(task.to_dict())
    url = blob.get_url(is_public=False)
    return redirect(url, code=307)
