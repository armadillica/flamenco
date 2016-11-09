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
from flamenco.node_types.manager import node_type_manager
from flamenco import current_flamenco, ROLES_REQUIRED_TO_VIEW_ITEMS

blueprint = Blueprint('flamenco.managers', __name__, url_prefix='/managers')
perproject_blueprint = Blueprint('flamenco.managers.perproject', __name__,
                                 url_prefix='/<project_url>/managers')
log = logging.getLogger(__name__)


@blueprint.route('/')
def index():
    user = flask_login.current_user
    if not user.is_authenticated:
        return render_template('flamenco/managers/index.html')

    managers = current_flamenco.manager_manager.managers_for_user(user.objectid)
    return render_template('flamenco/managers/for_user.html',
                           managers=managers['_items'],
                           manager_count=managers['_meta']['total'])


@blueprint.route('/<manager_id>', methods=['DELETE'])
def delete(manager_id):
    log.info('Deleting manager %s', manager_id)

    etag = request.form['etag']
    current_flamenco.manager_manager.delete_manager(manager_id, etag)

    return '', 204


@perproject_blueprint.route('/', endpoint='index')
@flamenco_project_view()
def for_project(project, manager_id=None):
    managers = current_flamenco.manager_manager.managers_for_project(project['_id'])
    return render_template('flamenco/managers/for_project.html',
                           managers=managers['_items'],
                           open_manager_id=manager_id,
                           project=project)


@perproject_blueprint.route('/<manager_id>')
@flamenco_project_view(extension_props=True)
def view_manager(project, flamenco_props, manager_id):
    if not request.is_xhr:
        return for_project(project, manager_id=manager_id)

    # Manager list is public, manager details are not.
    if not flask_login.current_user.has_role(*ROLES_REQUIRED_TO_VIEW_ITEMS):
        raise wz_exceptions.Forbidden()

    api = pillar_api()
    manager = pillarsdk.Node.find(manager_id, api=api)
    node_type = project.get_node_type(node_type_manager['name'])

    # Fetch project users so that we can assign them managers
    if 'PUT' in manager.allowed_methods:
        users = project.get_users(api=api)
        project.users = users['_items']
    else:
        manager.properties.assigned_to.users = [pillar.web.subquery.get_user_info(uid)
                                             for uid in manager.properties.assigned_to.users]

    return render_template('flamenco/managers/view_manager_embed.html',
                           manager=manager,
                           project=project,
                           manager_node_type=node_type,
                           flamenco_props=flamenco_props.to_dict(),
                           flamenco_context=request.args.get('context'))


@perproject_blueprint.route('/<manager_id>', methods=['POST'])
@flamenco_project_view()
def save(project, manager_id):
    log.info('Saving manager %s', manager_id)
    log.debug('Form data: %s', request.form)

    manager_dict = request.form.to_dict()
    manager_dict['users'] = request.form.getlist('users')

    manager = current_flamenco.manager_manager.edit_manager(manager_id, **manager_dict)

    return pillar.api.utils.jsonify(manager.to_dict())


@perproject_blueprint.route('/create', methods=['POST'])
@flamenco_project_view()
def create_manager(project):
    manager_type = request.form['manager_type']
    parent = request.form.get('parent', None)

    manager = current_flamenco.manager_manager.create_manager(project,
                                                    manager_type=manager_type,
                                                    parent=parent)

    resp = flask.make_response()
    resp.headers['Location'] = flask.url_for('.view_manager',
                                             project_url=project['url'],
                                             manager_id=manager['_id'])
    resp.status_code = 201

    return flask.make_response(flask.jsonify({'manager_id': manager['_id']}), 201)


@perproject_blueprint.route('/<manager_id>/activities')
@flamenco_project_view()
def activities(project, manager_id):
    if not request.is_xhr:
        return flask.redirect(flask.url_for('.view_manager',
                                            project_url=project.url,
                                            manager_id=manager_id))

    acts = current_flamenco.activities_for_node(manager_id)
    return flask.render_template('flamenco/managers/view_activities_embed.html',
                                 activities=acts)
