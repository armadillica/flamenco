# -*- encoding: utf-8 -*-

import logging

import werkzeug.exceptions as wz_exceptions

from pillar.api.utils.authorization import check_permissions, user_has_role

log = logging.getLogger(__name__)


def check_task_permission_fetch(task_doc):
    from flamenco import current_flamenco

    if user_has_role(u'admin'):
        return

    if not current_flamenco.manager_manager.user_is_manager():
        # FIXME: Regular user, undefined behaviour as of yet.
        # # Run validation process, since GET on nodes entry point is public
        # check_permissions('flamenco_tasks', task_doc, 'GET',
        #                   append_allowed_methods=True)
        raise wz_exceptions.Forbidden()

    # Managers should not have direct access to tasks; use scheduler instead.
    raise wz_exceptions.Forbidden()


def check_task_permission_fetch_resource(response):
    from flamenco import current_flamenco

    if user_has_role(u'admin'):
        return

    if not current_flamenco.manager_manager.user_is_manager():
        # FIXME: Regular user, undefined behaviour as of yet.
        # # Run validation process, since GET on nodes entry point is public
        # check_permissions('flamenco_tasks', task_doc, 'GET',
        #                   append_allowed_methods=True)
        raise wz_exceptions.Forbidden()

    # Managers should not have direct access to tasks; use scheduler instead.
    raise wz_exceptions.Forbidden()


def check_task_permissions_create_delete(task_doc, original_doc=None):
    """For now, only admins are allowed to create and delete tasks."""

    if not user_has_role(u'admin'):
        raise wz_exceptions.Forbidden()

    # FIXME: check user access to the project.


def check_task_permissions_edit(task_doc, original_doc=None):
    """For now, only admins and owning managers are allowed to edit."""

    if not user_has_role(u'admin'):
        raise wz_exceptions.Forbidden()

    # FIXME: check user access to the project.


def setup_app(app):
    app.on_fetched_item_flamenco_tasks += check_task_permission_fetch
    app.on_fetched_resource_flamenco_tasks += check_task_permission_fetch_resource

    app.on_insert_flamenco_tasks += check_task_permissions_create_delete
    app.on_delete_flamenco_tasks += check_task_permissions_create_delete
    app.on_update_flamenco_tasks += check_task_permissions_edit
    app.on_replace_flamenco_tasks += check_task_permissions_edit
