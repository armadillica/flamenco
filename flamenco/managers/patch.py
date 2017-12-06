"""Manager patching support."""

import logging

import bson
from flask import Blueprint, jsonify
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils.authentication import current_user_id
from pillar.api.utils import authorization, str2id
from pillar.api import patch_handler
from pillar import current_app

from .. import current_flamenco

log = logging.getLogger(__name__)
patch_api_blueprint = Blueprint('flamenco.managers.patch', __name__)


class ManagerPatchHandler(patch_handler.AbstractPatchHandler):
    item_name = 'manager'

    def _assign_or_remove_project(self, manager_id: bson.ObjectId, patch: dict, action: str):
        """Assigns a manager to a project or removes it.

        The calling user must be owner of the manager (always)
        and member of the project (if assigning).
        """

        from pillar.api.projects.utils import user_rights_in_project

        from flamenco import current_flamenco

        try:
            project_strid = patch['project']
        except KeyError:
            log.warning('User %s sent invalid PATCH %r for manager %s.',
                        current_user_id(), patch, manager_id)
            raise wz_exceptions.BadRequest('Missing key "project"')

        project_id = str2id(project_strid)

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

    @authorization.require_login(require_cap='flamenco-use')
    def patch_assign_to_project(self, manager_id: bson.ObjectId, patch: dict):
        """Assigns a manager to a project.

        The calling user must be owner of the manager and member of the project.
        """

        return self._assign_or_remove_project(manager_id, patch, 'assign')

    @authorization.require_login(require_cap='flamenco-use')
    def patch_remove_from_project(self, manager_id: bson.ObjectId, patch: dict):
        """Unassigns a manager from a project.

        The calling user must be owner of the manager.
        """

        return self._assign_or_remove_project(manager_id, patch, 'remove')

    @authorization.require_login(require_cap='flamenco-use')
    def patch_edit_from_web(self, manager_id: bson.ObjectId, patch: dict):
        """Updates Manager fields from the web."""

        from pymongo.results import UpdateResult

        if not current_flamenco.manager_manager.user_is_owner(mngr_doc_id=manager_id):
            log.warning('User %s uses PATCH to edit manager %s, '
                        'but user is not owner of that Manager. Request denied.',
                        current_user_id(), manager_id)
            raise wz_exceptions.Forbidden()

        # Only take known fields from the patch, don't just copy everything.
        update = {'name': patch['name'],
                  'description': patch['description']}
        self.log.info('User %s edits Manager %s: %s', current_user_id(), manager_id, update)

        validator = current_app.validator_for_resource('flamenco_managers')
        if not validator.validate_update(update, manager_id):
            resp = jsonify({
                '_errors': validator.errors,
                '_message': ', '.join(f'{field}: {error}'
                                      for field, error in validator.errors.items()),
            })
            resp.status_code = 422
            return resp

        managers_coll = current_flamenco.db('managers')
        result: UpdateResult = managers_coll.update_one(
            {'_id': manager_id},
            {'$set': update}
        )

        if result.matched_count != 1:
            self.log.warning('User %s edits Manager %s but update matched %i items',
                             current_user_id(), manager_id, result.matched_count)
            raise wz_exceptions.BadRequest()

        return '', 204

    @authorization.require_login(require_cap='flamenco-use')
    def patch_change_ownership(self, manager_id: bson.ObjectId, patch: dict):
        """Shares or un-shares the Manager with a user."""

        man_man = current_flamenco.manager_manager
        if not man_man.user_is_owner(mngr_doc_id=manager_id):
            log.warning('User %s uses PATCH to (un)share manager %s, '
                        'but user is not owner of that Manager. Request denied.',
                        current_user_id(), manager_id)
            raise wz_exceptions.Forbidden()

        action = patch.get('action', '')
        try:
            action = man_man.ShareAction[action]
        except KeyError:
            raise wz_exceptions.BadRequest(f'Unknown action {action!r}')

        subject_uid = str2id(patch.get('user', ''))
        if action == man_man.ShareAction.share and subject_uid == current_user_id():
            log.warning('%s tries to %s Manager %s with itself',
                        current_user_id(), action, manager_id)
            raise wz_exceptions.BadRequest(f'Cannot share a Manager with yourself')

        if action == man_man.ShareAction.share and \
                not current_flamenco.auth.user_is_flamenco_user(subject_uid):
            log.warning('%s Manager %s on behalf of user %s, but subject user %s '
                        'is not Flamenco user', action, manager_id, current_user_id(),
                        subject_uid)
            raise wz_exceptions.Forbidden(f'User {subject_uid} is not allowed to use Flamenco')

        try:
            man_man.share_unshare_manager(manager_id, action, subject_uid)
        except ValueError as ex:
            raise wz_exceptions.BadRequest(str(ex))


def setup_app(app):
    ManagerPatchHandler(patch_api_blueprint)
    app.register_api_blueprint(patch_api_blueprint, url_prefix='/flamenco/managers')
