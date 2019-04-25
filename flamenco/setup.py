"""Setting up projects for Flamenco."""

import logging

from flask import current_app

from . import EXTENSION_NAME, current_flamenco
from pillar.api.projects.utils import get_project, put_project

log = logging.getLogger(__name__)


def setup_for_flamenco(project_url):
    """Add extension properties for Flamenco.

    :return: The updated project.
    """

    project = get_project(project_url)

    # Set default extension properties. Be careful not to overwrite any
    # properties that are already there.
    eprops = project.setdefault('extension_props', {})
    eprops.setdefault(EXTENSION_NAME, {})

    put_project(project)

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
