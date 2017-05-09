# -*- encoding: utf-8 -*-

import logging

import werkzeug.exceptions as wz_exceptions

from flamenco import current_flamenco

log = logging.getLogger(__name__)


def check_manager_permissions(mngr_doc):
    if current_flamenco.manager_manager.user_manages(mngr_doc=mngr_doc):
        log.debug('Allowing manager access to own document.')
        return

    if current_flamenco.manager_manager.user_may_use(mngr_doc=mngr_doc):
        return

    from pillar.api.utils.authentication import current_user_id

    log.info('Denying access to Manager %s to user %s',
             mngr_doc.get('_id'), current_user_id())
    raise wz_exceptions.Forbidden()


def check_manager_permissions_modify(mngr_doc, original_doc=None):
    """For now, only admins are allowed to create, edit, and delete managers.

    Other operations (assigning to projects, etc.) should use a PATCH call.
    """

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
        # TODO: filter on user groups.
        querying_single = bool(lookup.get('_id'))
        if not querying_single:
            # Querying for a list of managers; limit that to Owned managers.
            lookup['owner'] = {'$in': current_user['groups']}

    log.debug('Filtering on %s', lookup)


def setup_app(app):
    app.on_pre_GET_flamenco_managers += pre_get_flamenco_managers
    app.on_fetched_item_flamenco_managers += check_manager_permissions
    app.on_insert_flamenco_managers += check_manager_permissions_modify
    app.on_update_flamenco_managers += check_manager_permissions_modify
    app.on_replace_flamenco_managers += check_manager_permissions_modify
    app.on_delete_flamenco_managers += check_manager_permissions_modify
