import logging

import attr
from flask import Blueprint, render_template, request, jsonify
import flask_wtf.csrf
import werkzeug.exceptions as wz_exceptions

from pillarsdk import User

import pillar.flask_extra
from pillar.api.utils import authorization, str2id, gravatar
from pillar.web.system_util import pillar_api
from pillar.api.utils.authentication import current_user_id
from pillar.api.utils.authorization import user_matches_roles

import flamenco.auth

from .sdk import Manager
from .. import current_flamenco

log = logging.getLogger(__name__)
blueprint = Blueprint('flamenco.managers', __name__, url_prefix='/managers')


@blueprint.route('/', endpoint='index')
def index(manager_id: str = None):
    api = pillar_api()

    managers = Manager.all(api=api)

    if not manager_id and managers['_items']:
        manager_id = managers['_items'][0]._id

    manager_limit_reached = managers['_meta']['total'] >= flamenco.auth.MAX_MANAGERS_PER_USER

    # TODO Sybren: move this to a utility function + check on endpoint to create manager
    has_flamenco_role = user_matches_roles(flamenco.auth.ROLES_REQUIRED_TO_USE_FLAMENCO)
    has_flamenco_view_role = user_matches_roles(flamenco.auth.ROLES_REQUIRED_TO_VIEW_FLAMENCO)
    can_create_manager = has_flamenco_role and has_flamenco_view_role and not manager_limit_reached

    return render_template('flamenco/managers/index.html',
                           manager_limit_reached=manager_limit_reached,
                           has_flamenco_role=has_flamenco_role,
                           has_flamenco_view_role=has_flamenco_view_role,
                           can_create_manager=can_create_manager,
                           max_managers=flamenco.auth.MAX_MANAGERS_PER_USER,
                           managers=managers,
                           open_manager_id=manager_id)


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
                           manager=manager,
                           can_edit=can_edit,
                           available_projects=available_projects,
                           linked_projects=linked_projects,
                           owners=owners,
                           can_abandon_manager=len(owners) > 1,
                           csrf=csrf)


@blueprint.route('/create-new', methods=['POST'])
@authorization.require_login(require_roles=flamenco.auth.ROLES_REQUIRED_TO_USE_FLAMENCO)
def create_new():
    """Creates a new Flamenco Manager, owned by the currently logged-in user."""

    from pillar.api.service import ServiceAccountCreationError

    user_id = current_user_id()
    log.info('Creating new manager for user %s', user_id)

    name = request.form['name']
    description = request.form['description']

    try:
        current_flamenco.manager_manager.create_new_manager(name, description, user_id)
    except ServiceAccountCreationError as ex:
        log.error('Unable to create service account for Manager (current user=%s): %s',
                  current_user_id(), ex)
        return 'Error creating service account', 500

    return '', 204


@blueprint.route('/<manager_id>/auth-token', methods=['POST'])
@authorization.require_login(require_roles=flamenco.auth.ROLES_REQUIRED_TO_USE_FLAMENCO)
def manager_auth_token(manager_id):
    """Returns the Manager's authentication token.

    Only allowed by owners of the Manager.
    """

    manager_oid = str2id(manager_id)

    csrf = request.form.get('csrf', '')
    if not flask_wtf.csrf.validate_csrf(csrf):
        log.warning('User %s tried to get authentication token for Manager %s without '
                    'valid CSRF token!', current_user_id(), manager_oid)
        raise wz_exceptions.PreconditionFailed()

    if not current_flamenco.manager_manager.user_is_owner(mngr_doc_id=manager_oid):
        log.warning('User %s wants to get authentication token of manager %s, '
                    'but user is not owner of that Manager. Request denied.',
                    current_user_id(), manager_oid)
        raise wz_exceptions.Forbidden()

    auth_token_info = current_flamenco.manager_manager.auth_token(manager_oid)
    if not auth_token_info:
        raise wz_exceptions.NotFound()

    return jsonify(attr.asdict(auth_token_info))


@blueprint.route('/<manager_id>/generate-auth-token', methods=['POST'])
@authorization.require_login(require_roles=flamenco.auth.ROLES_REQUIRED_TO_USE_FLAMENCO)
def generate_auth_token(manager_id):
    """Revokes the Manager's existing authentication tokens and generates a new one.

    Only allowed by owners of the Manager.
    """

    manager_oid = str2id(manager_id)

    csrf = request.form.get('csrf', '')
    if not flask_wtf.csrf.validate_csrf(csrf):
        log.warning('User %s tried to generate authentication token for Manager %s without '
                    'valid CSRF token!', current_user_id(), manager_oid)
        raise wz_exceptions.PreconditionFailed()

    if not current_flamenco.manager_manager.user_is_owner(mngr_doc_id=manager_oid):
        log.warning('User %s wants to generate authentication token of manager %s, '
                    'but user is not owner of that Manager. Request denied.',
                    current_user_id(), manager_oid)
        raise wz_exceptions.Forbidden()

    auth_token_info = current_flamenco.manager_manager.gen_new_auth_token(manager_oid)
    if not auth_token_info:
        raise wz_exceptions.NotFound()

    return jsonify(attr.asdict(auth_token_info))
