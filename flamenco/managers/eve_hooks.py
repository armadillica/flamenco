import collections
import logging
import re
import typing

import werkzeug.exceptions as wz_exceptions

from pillar.auth import current_user

from flamenco import current_flamenco, blender_cloud_addon

log = logging.getLogger(__name__)
field_name_escape_replace = re.compile('[.$]')


def check_manager_permissions(mngr_doc):
    if current_flamenco.manager_manager.user_manages(mngr_doc=mngr_doc):
        log.debug('Allowing manager access to own document.')
        return

    if current_flamenco.manager_manager.user_may_use(mngr_doc=mngr_doc):
        return

    log.info('Denying access to Manager %s to user %s',
             mngr_doc.get('_id'), current_user.user_id)
    raise wz_exceptions.Forbidden()


def check_manager_resource_permissions(response):
    for manager_doc in response['_items']:
        check_manager_permissions(manager_doc)


def check_manager_permissions_create(mngr_doc):
    if not current_user.has_cap('flamenco-use'):
        log.info('Denying access to create Manager to user %s',
                 current_user.user_id)
        raise wz_exceptions.Forbidden()


def check_manager_permissions_modify(mngr_doc, original_doc=None):
    """For now, only admins are allowed to create, edit, and delete managers.

    Other operations (assigning to projects, etc.) should use a PATCH call.
    """

    if current_flamenco.manager_manager.user_may_use(mngr_doc=mngr_doc):
        return

    log.info('Denying access to edit Manager %s to user %s',
             mngr_doc.get('_id'), current_user.user_id)
    raise wz_exceptions.Forbidden()


def pre_get_flamenco_managers(request, lookup):
    """Filter returned Flamenco managers."""

    if current_user.is_anonymous:
        log.warning('Disallowing anonymous access to list of managers.')
        raise wz_exceptions.Forbidden()

    # Flamenco Admins can see everything
    if current_flamenco.auth.current_user_is_flamenco_admin():
        return

    if current_flamenco.auth.current_user_is_flamenco_manager():
        # If this user is a Flamenco Manager, just return its own document.
        lookup['service_account'] = current_user.user_id
    else:
        querying_single = bool(lookup.get('_id') or request.args.get('_id'))
        if not querying_single:
            # Querying for a list of managers; limit that to Owned managers.
            lookup['owner'] = {'$in': current_user['groups']}

    log.debug('Filtering on %s', lookup)


def rewrite_manager_settings(doc: dict):
    """Update the Manager's variables to be compatible with the Blender Cloud add-on.

    The Blender Cloud Add-on only implemented versioning of Manager settings in
    1.13, so if an older version requests the Manager just transform it to a version
    the add-on understands.
    """

    # Make sure the version is always explicit.
    doc.setdefault('settings_version', 1)

    addon_version = blender_cloud_addon.requested_by_version()
    if not addon_version or addon_version >= (1, 12, 2):
        return

    # Downgrade settings for this old add-on version.
    # Since it's the Blender Cloud add-on, we're targeting the 'users' audience.
    audiences = {'', 'all', 'users'}

    # variable name -> platform -> value
    oneway = collections.defaultdict(lambda: collections.defaultdict(dict))
    twoway = collections.defaultdict(lambda: collections.defaultdict(dict))
    target_maps = {
        'oneway': oneway,
        'twoway': twoway,
    }

    for name, variable in doc.get('variables', {}).items():
        direction = variable.get('direction', 'oneway')
        target_map = target_maps.get(direction, oneway)

        for value in variable['values']:
            if value['audience'] not in audiences:
                continue

            if value.get('platform'):
                target_map[name][value['platform']] = value['value']

            for platform in value.get('platforms', []):
                target_map[name][platform] = value['value']

    doc['variables'] = oneway
    doc['path_replacement'] = twoway
    doc['settings_version'] = 1


def rewrite_managers_settings(response: dict):
    for manager in response['_items']:
        manager.setdefault('settings_version', 1)
        rewrite_manager_settings(manager)


def setup_app(app):
    app.on_pre_GET_flamenco_managers += pre_get_flamenco_managers
    app.on_fetched_item_flamenco_managers += check_manager_permissions
    app.on_fetched_item_flamenco_managers += rewrite_manager_settings
    app.on_fetched_resource_flamenco_managers += check_manager_resource_permissions
    app.on_fetched_resource_flamenco_managers += rewrite_managers_settings
    app.on_insert_flamenco_managers += check_manager_permissions_create
    app.on_update_flamenco_managers += check_manager_permissions_modify
    app.on_replace_flamenco_managers += check_manager_permissions_modify
    app.on_delete_flamenco_managers += check_manager_permissions_modify
