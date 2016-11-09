"""Commandline interface for Attract."""

import logging

from flask import current_app

from pillar.cli import manager, create_service_account
from pillar.api.utils import authentication

import attract.setup

log = logging.getLogger(__name__)


@manager.command
@manager.option('-r', '--replace', dest='replace', action='store_true', default=False)
@manager.option('-s', '--svn', dest='svn_url', nargs='?')
def setup_for_attract(project_url, replace=False, svn_url=None):
    """Adds Attract node types to the project.

    Use --replace to replace pre-existing Attract node types
    (by default already existing Attract node types are skipped).
    """

    authentication.force_cli_user()
    attract.setup.setup_for_attract(project_url, replace=replace, svn_url=svn_url)


@manager.command
def create_svner_account(email, project_url):
    """Creates an account that can push SVN activity to an Attract project.

    :param email: email address associated with the account
    :param project_url:
    """

    authentication.force_cli_user()

    projs_coll = current_app.db()['projects']
    proj = projs_coll.find_one({'url': project_url},
                               projection={'_id': 1})
    if not proj:
        log.error('Unable to find project url=%s', project_url)
        return 1

    account, token = create_service_account(email, [u'svner'], {'svner': {'project': proj['_id']}})
    return account, token
