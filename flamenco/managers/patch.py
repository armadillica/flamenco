"""Manager patching support."""

import logging

import bson
from flask import Blueprint
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils import authorization
from pillar.api import patch_handler

log = logging.getLogger(__name__)
patch_api_blueprint = Blueprint('flamenco.managers.patch', __name__)


class ManagerPatchHandler(patch_handler.AbstractPatchHandler):
    item_name = 'manager'

    def _assign_or_remove_project(self, manager_id: bson.ObjectId, patch: dict, action: str):
        """Assigns a manager to a project or removes it.

        The calling user must be owner of the manager (always)
        and member of the project (if assigning).
        """

        from pillar.api.utils.authentication import current_user_id
        from pillar.api.utils import str2id
        from pillar.api.projects.utils import user_rights_in_project

        from flamenco import current_flamenco

        project_id = str2id(patch['project'])

        if not current_flamenco.manager_manager.user_is_owner(mngr_doc_id=manager_id):
            log.warning('User %s uses PATCH to %s manager %s to/from project %s, '
                        'but user is not owner of that Manager. Request denied.',
                        current_user_id(), action, manager_id, project_id)
            raise wz_exceptions.Forbidden()

        # Removing from a project doesn't require project membership.
        if action != 'remove':
            methods = user_rights_in_project(project_id)
            if 'PUT' not in methods:
                log.warning('User %s uses PATCH to %s manager %s to/from project %s, '
                            'but only has %s rights on project. Request denied.',
                            current_user_id(), action, manager_id, project_id, ', '.join(methods))
                raise wz_exceptions.Forbidden()

        log.info('User %s uses PATCH to %s manager %s to/from project %s',
                 current_user_id(), action, manager_id, project_id)

        ok = current_flamenco.manager_manager.api_assign_to_project(
            manager_id, project_id, action)
        if not ok:
            # Manager Manager will have already logged the cause.
            raise wz_exceptions.InternalServerError()

    @authorization.require_login()
    def patch_assign_to_project(self, manager_id: bson.ObjectId, patch: dict):
        """Assigns a manager to a project.

        The calling user must be owner of the manager and member of the project.
        """

        return self._assign_or_remove_project(manager_id, patch, 'assign')

    @authorization.require_login()
    def patch_remove_from_project(self, manager_id: bson.ObjectId, patch: dict):
        """Unassigns a manager from a project.

        The calling user must be owner of the manager.
        """

        return self._assign_or_remove_project(manager_id, patch, 'remove')


def setup_app(app):
    ManagerPatchHandler(patch_api_blueprint)
    app.register_api_blueprint(patch_api_blueprint, url_prefix='/flamenco/managers')
