import logging

from flask import Blueprint, render_template, request
import flask_login
import werkzeug.exceptions as wz_exceptions

from pillar.web.system_util import pillar_api

from flamenco.routes import flamenco_project_view
from flamenco import current_flamenco, ROLES_REQUIRED_TO_VIEW_ITEMS

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
    return render_template('flamenco/tasks/view_task_embed.html',
                           task=task,
                           project=project,
                           flamenco_props=flamenco_props.to_dict(),
                           flamenco_context=request.args.get('context'))
