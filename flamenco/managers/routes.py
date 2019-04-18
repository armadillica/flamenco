import logging

import attr
from flask import Blueprint, render_template, request, jsonify, session
import flask_wtf.csrf
import werkzeug.exceptions as wz_exceptions

from pillar import current_app
from pillar.web.projects.routes import project_navigation_links
from pillarsdk import User, Project

import pillar.flask_extra
from pillar.api.utils import authorization, str2id, gravatar
from pillar.web.system_util import pillar_api
from pillar.auth import current_user

import flamenco.auth

from .sdk import Manager
from .. import current_flamenco

log = logging.getLogger(__name__)
blueprint = Blueprint('flamenco.managers', __name__, url_prefix='/managers')


@blueprint.route('/', endpoint='index')
def index(manager_id: str = None):
    api = pillar_api()

    if current_user.is_authenticated:
        params = {'where': {'owner': {'$in': current_user.groups}}}
    else:
        params = None
    managers = Manager.all(params=params, api=api)

    if not manager_id and managers['_items']:
        manager_id = managers['_items'][0]._id

    manager_limit_reached = managers['_meta']['total'] >= flamenco.auth.MAX_MANAGERS_PER_USER

    # TODO Sybren: move this to a utility function + check on endpoint to create manager
    may_use_flamenco = current_user.has_cap('flamenco-use')
    can_create_manager = may_use_flamenco and (
            not manager_limit_reached or current_user.has_cap('admin'))

    if session.get('flamenco_last_project'):
        project = Project(session.get('flamenco_last_project'))
        navigation_links = project_navigation_links(project, pillar_api())
        extension_sidebar_links = current_app.extension_sidebar_links(project)
    else:
        project = None
        navigation_links = []
        extension_sidebar_links = []

    return render_template('flamenco/managers/index.html',
                           manager_limit_reached=manager_limit_reached,
                           may_use_flamenco=may_use_flamenco,
                           can_create_manager=can_create_manager,
                           max_managers=flamenco.auth.MAX_MANAGERS_PER_USER,
                           managers=managers,
                           open_manager_id=manager_id,
                           project=project,
                           navigation_links=navigation_links,
                           extension_sidebar_links=extension_sidebar_links)


@blueprint.route('/<manager_id>')
@pillar.flask_extra.vary_xhr()
def view_embed(manager_id: str):
    if not request.is_xhr:
        return index(manager_id)

    api = pillar_api()

    manager: Manager = Manager.find(manager_id, api=api)
    linked_projects = manager.linked_projects(api=api)
    linked_project_ids = set(manager.projects or [])

    # TODO: support pagination
    fetched = current_flamenco.flamenco_projects(
        projection={
            '_id': 1,
            'url': 1,
            'name': 1,
        })
    available_projects = [project
                          for project in fetched._items
                          if project['_id'] not in linked_project_ids]

    owner_gid = str2id(manager['owner'])
    owners = current_flamenco.manager_manager.owning_users(owner_gid)

    for owner in owners:
        owner['avatar'] = gravatar(owner.get('email'))
        owner['_id'] = str(owner['_id'])

    manager_oid = str2id(manager_id)
    can_edit = current_flamenco.manager_manager.user_is_owner(mngr_doc_id=manager_oid)

    csrf = flask_wtf.csrf.generate_csrf()

    return render_template('flamenco/managers/view_manager_embed.html',
                           manager=manager.to_dict(),
                           can_edit=can_edit,
                           available_projects=available_projects,
                           linked_projects=linked_projects,
                           owners=owners,
                           can_abandon_manager=len(owners) > 1,
                           csrf=csrf)


@blueprint.route('/create-new', methods=['POST'])
@authorization.require_login(require_cap='flamenco-use')
def create_new():
    """Creates a new Flamenco Manager, owned by the currently logged-in user."""

    from pillar.api.service import ServiceAccountCreationError

    user_id = current_user.user_id
    log.info('Creating new manager for user %s', user_id)

    name = request.form['name']
    description = request.form['description']

    try:
        current_flamenco.manager_manager.create_new_manager(name, description, user_id)
    except ServiceAccountCreationError as ex:
        log.error('Unable to create service account for Manager (current user=%s): %s',
                  current_user.user_id, ex)
        return 'Error creating service account', 500

    return '', 204


@blueprint.route('/<manager_id>/revoke-auth-token', methods=['POST'])
@authorization.require_login(require_cap='flamenco-use')
def revoke_auth_token(manager_id):
    """Revokes the Manager's existing authentication tokens.

    Only allowed by owners of the Manager.
    """

    manager_oid = str2id(manager_id)

    csrf = request.form.get('csrf', '')
    if not flask_wtf.csrf.validate_csrf(csrf):
        log.warning('User %s tried to generate authentication token for Manager %s without '
                    'valid CSRF token!', current_user.user_id, manager_oid)
        raise wz_exceptions.PreconditionFailed()

    if not current_flamenco.manager_manager.user_is_owner(mngr_doc_id=manager_oid):
        log.warning('User %s wants to generate authentication token of manager %s, '
                    'but user is not owner of that Manager. Request denied.',
                    current_user.user_id, manager_oid)
        raise wz_exceptions.Forbidden()

    current_flamenco.manager_manager.revoke_auth_token(manager_oid)
    return '', 204
