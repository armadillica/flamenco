"""Commandline interface for Flamenco."""

import logging

from flask import current_app
from flask_script import Manager

from pillar.cli import manager, create_service_account
from pillar.api.utils import authentication

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

manager.add_command("flamenco", manager_flamenco)
