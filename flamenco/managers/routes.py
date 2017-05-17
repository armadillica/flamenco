import logging

from flask import Blueprint, render_template, request

import pillar.flask_extra
from pillar.api.utils import authorization
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
    has_flamenco_role = user_matches_roles(flamenco.auth.ROLES_REQUIRED_TO_USE_FLAMENCO)
    can_create_manager = has_flamenco_role and not manager_limit_reached

    return render_template('flamenco/managers/index.html',
                           manager_limit_reached=manager_limit_reached,
                           has_flamenco_role=has_flamenco_role,
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

    return render_template('flamenco/managers/view_manager_embed.html',
                           manager=manager,
                           available_projects=available_projects,
                           linked_projects=linked_projects)


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
