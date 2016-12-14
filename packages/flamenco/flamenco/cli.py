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

    log.info('Created a new manager:\n%s', dumps(mngr_doc, indent=4))

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


manager.add_command("flamenco", manager_flamenco)
