"""Commandline interface for Flamenco."""

import logging

from flask import current_app
from flask_script import Manager

from pillar.cli import manager, create_service_account
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
    mngr_doc = flamenco.current_flamenco.manager_manager.create_manager(name, description)
    manager_id = mngr_doc['_id']

    print('Created a new manager:')
    print(dumps(mngr_doc, indent=4))

    service_name = u'flamenco_manager'

    def update_existing(service):
        if service_name in service:
            service[service_name].setdefault(u'managers', [])
            service[service_name][u'managers'].append(manager_id)
        else:
            service[service_name] = service_info

    service_info = {u'managers': [manager_id]}
    create_service_account(email,
                           [service_name],
                           {service_name: service_info},
                           update_existing=update_existing)


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
        u'CLI test job',
        u'Test job created from the server CLI',
        u'sleep',
        {
            'frames': '1-30, 40-44',
            'chunk_size': 13,
            'time_in_seconds': 3,
        },
        proj['_id'], user['_id'], manager_id)

    log.info('Job created:\n%s', dumps(job, indent=4))

manager.add_command("flamenco", manager_flamenco)
