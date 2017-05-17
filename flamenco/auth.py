"""Authorization management."""
import enum
import logging
import typing

import attr
import bson

import pillarsdk
from pillar import attrs_extra

# Roles required to view job, manager or task details.
ROLES_REQUIRED_TO_VIEW_ITEMS = {'demo', 'subscriber', 'admin', 'flamenco-admin', 'flamenco-user'}

# TODO: deal with log viewing through permissions too.
ROLES_REQUIRED_TO_VIEW_LOGS = {'admin', 'flamenco-admin'}

# Having either of these roles is minimum requirement for using Flamenco.
ROLES_REQUIRED_TO_USE_FLAMENCO = {'flamenco-user', 'flamenco-admin', 'admin'}
ROLES_REQUIRED_TO_VIEW_FLAMENCO = {'admin', 'subscriber', 'demo'}

# Having any of these methods on a project means you can use Flamenco.
# Prerequisite: the project is set up for Flamenco and has a Manager assigned to it.
PROJECT_METHODS_TO_USE_FLAMENCO = {'PUT'}


class Actions(enum.Enum):
    VIEW = 'view'
    USE = 'use'


# Required roles for a given action.
req_roles = {
    Actions.VIEW: ROLES_REQUIRED_TO_VIEW_FLAMENCO,
    Actions.USE: ROLES_REQUIRED_TO_USE_FLAMENCO
}


@attr.s
class Auth(object):
    """Handles authorization for Flamenco."""

    _log = attrs_extra.log('%s.Auth' % __name__)
    Actions = Actions  # this allows using current_flamenco.auth.Actions

    def current_user_is_flamenco_admin(self) -> bool:
        """Returns True iff the user is a Flamenco admin or regular admin."""

        from pillar.api.utils.authorization import user_matches_roles

        return user_matches_roles({'admin', 'flamenco-admin'})

    def current_user_is_flamenco_manager(self) -> bool:
        """Returns True iff the user is a Flamenco Manager."""

        from pillar.api.utils.authorization import user_matches_roles

        return user_matches_roles({'service', 'flamenco_manager'}, require_all=True)

    def current_user_may(self, action: Actions, project_id: bson.ObjectId) -> bool:
        """Returns True iff the user is authorised to use/view Flamenco on the given project.

        This is linked to the Managers assigned to this project. As a result, you cannot
        use Flamenco until one or more Managers is assigned.
        """

        from pillar.api.utils.authorization import user_matches_roles
        from pillar.api.utils.authentication import current_user_id
        from pillar.api.projects.utils import user_rights_in_project
        from flamenco import current_flamenco

        user_id = current_user_id()
        if not user_id:
            self._log.debug('Anonymous user never has access to Flamenco.')
            return False

        roles = req_roles[action]
        if not user_matches_roles(roles):
            self._log.info('User %s does not have either of roles %s required for action %s; '
                           'denying access to Flamenco', user_id, roles, action)
            return False

        # TODO Sybren: possibly split this up into a manager-fetching func + authorisation func.
        # TODO: possibly store the user rights on the current project in the current_user object?
        allowed_on_proj = user_rights_in_project(project_id)
        if not allowed_on_proj.intersection(PROJECT_METHODS_TO_USE_FLAMENCO):
            self._log.info('User %s has no %s access to project %s.',
                           user_id, PROJECT_METHODS_TO_USE_FLAMENCO, project_id)
            return False

        if self.current_user_is_flamenco_admin():
            self._log.debug('User is flamenco-admin, so has access to all Managers')
            return True

        managers_coll = current_flamenco.db('managers')
        managers = managers_coll.find({'projects': project_id})

        if self._log.isEnabledFor(logging.DEBUG):
            self._log.debug('User has access to the following managers for this project: %s',
                            [m['_id'] for m in managers])

        return managers.count() > 0
