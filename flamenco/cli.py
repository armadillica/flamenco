"""Commandline interface for Flamenco."""

import logging

from flask import current_app
from flask_script import Manager

from pillar.cli import manager
from pillar.api.utils import authentication

import flamenco
import flamenco.setup

log = logging.getLogger(__name__)

manager_flamenco = Manager(current_app, usage="Perform Flamenco operations")


@manager_flamenco.command
@manager_flamenco.option('-r', '--replace', dest='replace', action='store_true',
                         default=False)
def setup_for_flamenco(project_url, replace=False):
    """Adds Flamenco node types to the project.

    Use --replace to replace pre-existing Flamenco node types
    (by default already existing Flamenco node types are skipped).
    """

    authentication.force_cli_user()
    flamenco.setup.setup_for_flamenco(project_url, replace=replace)


@manager_flamenco.command
def create_manager(email, name, description):
    """Creates a Flamenco manager."""

    from pillar.api.utils import dumps

    authentication.force_cli_user()
    mngr_doc, account, token = flamenco.setup.create_manager(email, name, description)

    print('Created a new manager:')
    print(dumps(mngr_doc, indent=4))


@manager_flamenco.command
def assign_manager_project(manager_id, project_url):
    """Assigns a Flamenco Manager to a project."""

    _manager_project(manager_id, project_url, 'assign')


@manager_flamenco.command
def remove_manager_project(manager_id, project_url):
    """Removes a Flamenco Manager from a project."""

    _manager_project(manager_id, project_url, 'remove')


def _manager_project(manager_id, project_url, action):
    from pillar.api.utils import str2id
    from flamenco import current_flamenco

    authentication.force_cli_user()
    manager_id = str2id(manager_id)

    # Find project
    projs_coll = current_app.db()['projects']
    proj = projs_coll.find_one({'url': project_url}, projection={'_id': 1})
    if not proj:
        log.error('Unable to find project url=%s', project_url)
        return 1

    project_id = proj['_id']
    ok = current_flamenco.manager_manager.api_assign_to_project(manager_id, project_id, action)
    if not ok:
        log.error('Unable to assign manager %s to project %s', manager_id, project_id)
        return 1


@manager_flamenco.command
def create_test_job(manager_id, user_email, project_url):
    """Creates a test job for a given manager."""

    from pillar.api.utils import dumps, str2id

    manager_id = str2id(manager_id)
    authentication.force_cli_user()

    # Find user
    users_coll = current_app.db()['users']
    user = users_coll.find_one({'email': user_email}, projection={'_id': 1})
    if not user:
        raise ValueError('User with email %r not found' % user_email)

    # Find project
    projs_coll = current_app.db()['projects']
    proj = projs_coll.find_one({'url': project_url},
                               projection={'_id': 1})
    if not proj:
        log.error('Unable to find project url=%s', project_url)
        return 1

    # Create the job
    job = flamenco.current_flamenco.job_manager.api_create_job(
        'CLI test job',
        'Test job created from the server CLI',
        'sleep',
        {
            'frames': '1-30, 40-44',
            'chunk_size': 13,
            'time_in_seconds': 3,
        },
        proj['_id'], user['_id'], manager_id)

    log.info('Job created:\n%s', dumps(job, indent=4))


@manager_flamenco.command
def make_admin(user_email):
    """Grants the user flamenco-admin role."""

    from pillar.api.service import do_badger

    _, status = do_badger('grant', role='flamenco-admin', user_email=user_email)
    if status != 204:
        log.error('Unable to find user %s', user_email)
        return 1

    log.info('Done.')
    return 0


@manager_flamenco.command
def revoke_admin(user_email):
    """Revokes the user's flamenco-admin role."""

    from pillar.api.service import do_badger

    _, status = do_badger('revoke', role='flamenco-admin', user_email=user_email)
    if status != 204:
        log.error('Unable to find user %s', user_email)
        return 1

    log.info('Done.')
    return 0


manager.add_command("flamenco", manager_flamenco)
