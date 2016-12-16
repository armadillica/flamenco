# -*- encoding: utf-8 -*-

import logging
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils.authorization import user_has_role
from pillar.api.utils.authentication import current_user_id

log = logging.getLogger(__name__)


def check_manager_permissions(mngr_doc):
    from flamenco import current_flamenco

    if user_has_role(u'admin'):
        return

    if not current_flamenco.manager_manager.user_manages(mngr_doc=mngr_doc):
        raise wz_exceptions.Forbidden()

    log.debug('Allowing manager access to own document.')


def check_manager_permissions_modify(mngr_doc, original_doc=None):
    """For now, only admins are allowed to create, edit, and delete managers."""

    if not user_has_role(u'admin'):
        raise wz_exceptions.Forbidden()


def setup_app(app):
    app.on_fetched_item_flamenco_managers += check_manager_permissions
    app.on_insert_flamenco_managers += check_manager_permissions_modify
    app.on_update_flamenco_managers += check_manager_permissions_modify
    app.on_replace_flamenco_managers += check_manager_permissions_modify
    app.on_delete_flamenco_managers += check_manager_permissions_modify
