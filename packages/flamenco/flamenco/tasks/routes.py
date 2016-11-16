import logging

from flask import Blueprint, render_template, request, current_app
import flask
import flask_login
import werkzeug.exceptions as wz_exceptions

import pillarsdk
from pillar.web.system_util import pillar_api
import pillar.api.utils
import pillar.web.subquery

from flamenco.routes import flamenco_project_view
from flamenco import current_flamenco, ROLES_REQUIRED_TO_VIEW_ITEMS

blueprint = Blueprint('flamenco.tasks', __name__, url_prefix='/tasks')
perproject_blueprint = Blueprint('flamenco.tasks.perproject', __name__,
                                 url_prefix='/<project_url>/tasks')
log = logging.getLogger(__name__)


@blueprint.route('/')
def index():
    user = flask_login.current_user
    if not user.is_authenticated:
        return render_template('flamenco/tasks/index.html')

    tasks = current_flamenco.task_manager.tasks_for_user(user.objectid)
    return render_template('flamenco/tasks/for_user.html',
                           tasks=tasks['_items'],
                           task_count=tasks['_meta']['total'])


@blueprint.route('/<task_id>', methods=['DELETE'])
def delete(task_id):
    log.info('Deleting task %s', task_id)

    etag = request.form['etag']
    current_flamenco.task_manager.delete_task(task_id, etag)

    return '', 204


@perproject_blueprint.route('/', endpoint='index')
@flamenco_project_view()
def for_project(project, task_id=None):
    tasks = current_flamenco.task_manager.tasks_for_project(project['_id'])
    return render_template('flamenco/tasks/for_project.html',
                           tasks=tasks['_items'],
                           open_task_id=task_id,
                           project=project)


@perproject_blueprint.route('/<task_id>')
@flamenco_project_view(extension_props=True)
def view_task(project, flamenco_props, task_id):
    if not request.is_xhr:
        return for_project(project, task_id=task_id)

    # Task list is public, task details are not.
    if not flask_login.current_user.has_role(*ROLES_REQUIRED_TO_VIEW_ITEMS):
        raise wz_exceptions.Forbidden()

    api = pillar_api()
    task = pillarsdk.Node.find(task_id, api=api)

    # Fetch project users so that we can assign them tasks
    if 'PUT' in task.allowed_methods:
        users = project.get_users(api=api)
        project.users = users['_items']
    else:
        task.properties.assigned_to.users = [pillar.web.subquery.get_user_info(uid)
                                             for uid in task.properties.assigned_to.users]

    return render_template('flamenco/tasks/view_task_embed.html',
                           task=task,
                           project=project,
                           task_node_type=node_type,
                           flamenco_props=flamenco_props.to_dict(),
                           flamenco_context=request.args.get('context'))


@perproject_blueprint.route('/<task_id>', methods=['POST'])
@flamenco_project_view()
def save(project, task_id):
    log.info('Saving task %s', task_id)
    log.debug('Form data: %s', request.form)

    task_dict = request.form.to_dict()
    task_dict['users'] = request.form.getlist('users')

    task = current_flamenco.task_manager.edit_task(task_id, **task_dict)

    return pillar.api.utils.jsonify(task.to_dict())


@perproject_blueprint.route('/create', methods=['POST'])
@flamenco_project_view()
def create_task(project):
    task_type = request.form['task_type']
    parent = request.form.get('parent', None)

    task = current_flamenco.task_manager.create_task(project,
                                                    task_type=task_type,
                                                    parent=parent)

    resp = flask.make_response()
    resp.headers['Location'] = flask.url_for('.view_task',
                                             project_url=project['url'],
                                             task_id=task['_id'])
    resp.status_code = 201

    return flask.make_response(flask.jsonify({'task_id': task['_id']}), 201)


@perproject_blueprint.route('/<task_id>/activities')
@flamenco_project_view()
def activities(project, task_id):
    if not request.is_xhr:
        return flask.redirect(flask.url_for('.view_task',
                                            project_url=project.url,
                                            task_id=task_id))

    acts = current_flamenco.activities_for_node(task_id)
    return flask.render_template('flamenco/tasks/view_activities_embed.html',
                                 activities=acts)
