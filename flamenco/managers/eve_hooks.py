# -*- encoding: utf-8 -*-

import logging

import werkzeug.exceptions as wz_exceptions

from flamenco import current_flamenco

log = logging.getLogger(__name__)


def check_manager_permissions(mngr_doc):
    if current_flamenco.current_user_is_flamenco_admin():
        return

    if not current_flamenco.manager_manager.user_manages(mngr_doc=mngr_doc):
        raise wz_exceptions.Forbidden()

    log.debug('Allowing manager access to own document.')


def check_manager_permissions_modify(mngr_doc, original_doc=None):
    """For now, only admins are allowed to create, edit, and delete managers."""

    if not current_flamenco.current_user_is_flamenco_admin():
        raise wz_exceptions.Forbidden()


def pre_get_flamenco_managers(request, lookup):
    """Filter returned Flamenco managers."""

    from flask import g

    current_user = g.get('current_user')
    if not current_user:
        log.warning('Disallowing anonymous access to list of managers.')
        raise wz_exceptions.Forbidden()

    # Flamenco Admins can see everything
    if current_flamenco.current_user_is_flamenco_admin():
        return

    user_id = current_user['user_id']

    if current_flamenco.current_user_is_flamenco_manager():
        # If this user is a Flamenco Manager, just return its own document.
        lookup['service_account'] = user_id
    else:
        # Regular user, filter on by both project and owner group membership.
        # TODO Sybren: filter on project membership
        lookup['owner'] = {'$in': current_user['groups']}

    log.debug('Filtering on %s', lookup)


def setup_app(app):
    app.on_pre_GET_flamenco_managers += pre_get_flamenco_managers
    app.on_fetched_item_flamenco_managers += check_manager_permissions
    app.on_insert_flamenco_managers += check_manager_permissions_modify
    app.on_update_flamenco_managers += check_manager_permissions_modify
    app.on_replace_flamenco_managers += check_manager_permissions_modify
    app.on_delete_flamenco_managers += check_manager_permissions_modify
