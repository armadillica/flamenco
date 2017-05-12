import logging

from flask import Blueprint, render_template, request

import pillarsdk
import pillar.flask_extra
from pillar.web.system_util import pillar_api

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

    return render_template('flamenco/managers/index.html',
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
