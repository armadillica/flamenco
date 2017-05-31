"""Setting up projects for Flamenco.

This is intended to be used by the CLI and unittests only, not tested
for live/production situations.
"""

import logging

from bson import ObjectId
from flask import current_app

from . import EXTENSION_NAME, current_flamenco

log = logging.getLogger(__name__)


def _get_project(project_url):
    """Find a project in the database, or SystemExit()s.

    :param project_url: UUID of the project
    :type: str
    :return: the project
    :rtype: dict
    """

    projects_collection = current_app.data.driver.db['projects']

    # Find the project in the database.
    project = projects_collection.find_one({'url': project_url})
    if not project:
        raise RuntimeError('Project %s does not exist.' % project_url)

    return project


def _update_project(project):
    """Updates a project in the database, or SystemExit()s.

    :param project: the project data, should be the entire project document
    :type: dict
    :return: the project
    :rtype: dict
    """

    from pillar.api.utils import remove_private_keys

    project_id = ObjectId(project['_id'])
    project = remove_private_keys(project)
    result, _, _, status_code = current_app.put_internal('projects', project, _id=project_id)

    if status_code != 200:
        raise RuntimeError(f"Can't update project {project_id}, "
                           f"status {status_code} with issues: {result}")


def setup_for_flamenco(project_url, replace=False):
    """Adds Flamenco node types to the project.

    Use --replace to replace pre-existing Flamenco node types
    (by default already existing Flamenco node types are skipped).

    Returns the updated project.
    """

    # Copy permissions from the project, then give everyone with PUT
    # access also DELETE access.
    project = _get_project(project_url)

    # Set default extension properties. Be careful not to overwrite any
    # properties that are already there.
    eprops = project.setdefault('extension_props', {})
    eprops.setdefault(EXTENSION_NAME, {
        'managers': [],  # List of Flamenco manager IDs that have access to this project.
    })

    _update_project(project)

    log.info('Project %s was updated for Flamenco.', project_url)

    return project


def create_manager(owner_email, name, description):
    """Creates a Flamenco manager with service account.

    :returns: tuple (mngr_doc, account, token)
    """

    from pymongo.cursor import Cursor

    # Find the owner, to add it to the owner group afterward.
    possible_owners: Cursor = current_app.db('users').find(
        {'email': owner_email},
        {'_id': 1, 'full_name': 1})
    owner_count = possible_owners.count()
    if owner_count == 0:
        raise ValueError(f'No user found with email address {owner_email}; '
                         'cannot assign ownership of Manager')
    if owner_count > 1:
        raise ValueError(f'Multiple users ({owner_count}) found with email address {owner_email}; '
                         'cannot assign ownership of Manager')
    owner = possible_owners[0]
    owner_id = owner['_id']

    account, mngr_doc, token = current_flamenco.manager_manager.create_new_manager(
        name, description, owner_id)

    return mngr_doc, account, token
