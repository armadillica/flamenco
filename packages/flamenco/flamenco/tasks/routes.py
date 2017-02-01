# coding=utf-8
import logging

from flask import Blueprint, render_template, request
import flask_login
import werkzeug.exceptions as wz_exceptions

from pillar.web.system_util import pillar_api

from flamenco.routes import flamenco_project_view
from flamenco import current_flamenco, ROLES_REQUIRED_TO_VIEW_ITEMS, ROLES_REQUIRED_TO_VIEW_LOGS

TASK_LOG_PAGE_SIZE = 10

# The task statuses that can be set from the web-interface.
ALLOWED_TASK_STATUSES_FROM_WEB = {'cancel-requested', 'queued'}

perjob_blueprint = Blueprint('flamenco.tasks.perjob', __name__,
                             url_prefix='/<project_url>/jobs/<job_id>')
perproject_blueprint = Blueprint('flamenco.tasks.perproject', __name__,
                                 url_prefix='/<project_url>/tasks')
log = logging.getLogger(__name__)


@perproject_blueprint.route('/', endpoint='index')
@flamenco_project_view()
def list_for_project(project, task_id=None):
    tasks = current_flamenco.task_manager.tasks_for_project(project['_id'])
    return render_template('flamenco/tasks/list_for_project.html',
                           tasks=tasks['_items'],
                           open_task_id=task_id,
                           project=project)


@perjob_blueprint.route('/tasks')
@flamenco_project_view()
def list_for_job(project, job_id, task_id=None):
    tasks = current_flamenco.task_manager.tasks_for_job(job_id)
    return render_template('flamenco/tasks/list_for_job_embed.html',
                           tasks=tasks['_items'],
                           open_task_id=task_id,
                           project=project,
                           task_count=tasks['_meta']['total'])


@perproject_blueprint.route('/<task_id>')
@flask_login.login_required
@flamenco_project_view(extension_props=True)
def view_task(project, flamenco_props, task_id):
    from flamenco.tasks.sdk import Task

    api = pillar_api()

    if not request.is_xhr:
        # Render page that'll perform the XHR.
        from flamenco.jobs import routes as job_routes

        task = Task.find(task_id, {'projection': {'job': 1}}, api=api)
        return job_routes.for_project(project, job_id=task['job'], task_id=task_id)

    # Task list is public, task details are not.
    if not flask_login.current_user.has_role(*ROLES_REQUIRED_TO_VIEW_ITEMS):
        raise wz_exceptions.Forbidden()

    task = Task.find(task_id, api=api)

    from . import REQUEABLE_TASK_STATES
    write_access = current_flamenco.current_user_is_flamenco_admin()
    can_requeue_task = write_access and task['status'] in REQUEABLE_TASK_STATES

    return render_template('flamenco/tasks/view_task_embed.html',
                           task=task,
                           project=project,
                           flamenco_props=flamenco_props.to_dict(),
                           flamenco_context=request.args.get('context'),
                           can_requeue_task=can_requeue_task)


@perproject_blueprint.route('/<task_id>/set-status', methods=['POST'])
@flask_login.login_required
@flamenco_project_view(extension_props=False)
def set_task_status(project, task_id):
    from flask_login import current_user

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
@flamenco_project_view()
def view_task_log(project, task_id):
    """Shows a limited number of task log entries.

    Pass page=N (N≥1) to request further entries.
    """

    from pillarsdk import ResourceNotFound
    from pillar.web.utils import is_valid_id, last_page_index
    from flamenco.tasks.sdk import TaskLog

    if not is_valid_id(task_id):
        raise wz_exceptions.UnprocessableEntity()

    # Task list is public, task details are not.
    if not flask_login.current_user.has_role(*ROLES_REQUIRED_TO_VIEW_LOGS):
        raise wz_exceptions.Forbidden()

    page_idx = int(request.args.get('page', 1))
    api = pillar_api()
    try:
        logs = TaskLog.all({'where': {'task': task_id},
                            'page': page_idx,
                            'max_results': TASK_LOG_PAGE_SIZE},
                           api=api)
    except ResourceNotFound:
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
@flamenco_project_view()
def download_task_log(project, task_id):
    """Shows the entire task log as text/plain"""

    from flask import Response, current_app

    from pillar.web.utils import is_valid_id, last_page_index
    from flamenco.tasks.sdk import TaskLog

    if not is_valid_id(task_id):
        raise wz_exceptions.UnprocessableEntity()

    # Task list is public, task details are not.
    if not flask_login.current_user.has_role(*ROLES_REQUIRED_TO_VIEW_LOGS):
        raise wz_exceptions.Forbidden()

    # Required because the stream_log() generator will run outside the app context.
    app = current_app._get_current_object()
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
