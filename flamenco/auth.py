"""Authorization management."""
import enum
import logging

import attr
import bson

from pillar import attrs_extra
from pillar.auth import current_user

# Having any of these methods on a project means you can use Flamenco.
# Prerequisite: the project is set up for Flamenco and has a Manager assigned to it.
PROJECT_METHODS_TO_USE_FLAMENCO = {'PUT'}

MAX_MANAGERS_PER_USER = 3


class Actions(enum.Enum):
    VIEW = 'view'
    USE = 'use'


# Required roles for a given action.
req_cap = {
    Actions.VIEW: 'flamenco-view',
    Actions.USE: 'flamenco-use',
}


@attr.s
class Auth(object):
    """Handles authorization for Flamenco."""

    _log = attrs_extra.log('%s.Auth' % __name__)
    Actions = Actions  # this allows using current_flamenco.auth.Actions

    def current_user_is_flamenco_admin(self) -> bool:
        """Returns True iff the user is a Flamenco admin or regular admin."""

        return current_user.has_cap('flamenco-admin')

    def current_user_is_flamenco_manager(self) -> bool:
        """Returns True iff the user is a Flamenco Manager."""

        from pillar.api.utils.authorization import user_matches_roles

        return user_matches_roles({'service', 'flamenco_manager'}, require_all=True)

    def current_user_is_flamenco_user(self) -> bool:
        """Returns True iff the current user has Flamenco User role."""

        return current_user.has_cap('flamenco-use')

    def user_is_flamenco_user(self, user_id: bson.ObjectId) -> bool:
        """Returns True iff the user has Flamenco User role."""

        from pillar import current_app
        from pillar.auth import UserClass

        assert isinstance(user_id, bson.ObjectId)

        # TODO: move role/cap checking code to Pillar.
        users_coll = current_app.db('users')
        db_user = users_coll.find_one({'_id': user_id}, {'roles': 1})
        if not db_user:
            self._log.debug('user_is_flamenco_user: User %s not found', user_id)
            return False

        user = UserClass.construct('', db_user)
        return user.has_cap('flamenco-use')

    def current_user_may(self, action: Actions, project_id: bson.ObjectId) -> bool:
        """Returns True iff the user is authorised to use/view Flamenco on the given project.

        This is linked to the Managers assigned to this project. As a result, you cannot
        use Flamenco until one or more Managers is assigned.
        """

        from pillar.api.projects.utils import user_rights_in_project
        import pillar.auth
        from flamenco import current_flamenco

        # Get the actual user object to prevent multiple passes through the LocalProxy.
        user: pillar.auth.UserClass = current_user._get_current_object()
        if user.is_anonymous:
            self._log.debug('Anonymous user never has access to Flamenco.')
            return False

        cap = req_cap[action]
        if not user.has_cap(cap):
            self._log.info('User %s does not have capability %r required for action %s; '
                           'denying access to Flamenco', user.user_id, cap, action)
            return False

        # TODO Sybren: possibly split this up into a manager-fetching func + authorisation func.
        # TODO: possibly store the user rights on the current project in the current_user object?
        allowed_on_proj = user_rights_in_project(project_id)
        if not allowed_on_proj.intersection(PROJECT_METHODS_TO_USE_FLAMENCO):
            self._log.info('User %s has no %s access to project %s.',
                           user.user_id, PROJECT_METHODS_TO_USE_FLAMENCO, project_id)
            return False

        if user.has_cap('flamenco-admin'):
            self._log.debug('User is flamenco-admin, so has access to all Managers')
            return True

        managers_coll = current_flamenco.db('managers')
        managers = managers_coll.find({'projects': project_id})

        if self._log.isEnabledFor(logging.DEBUG):
            self._log.debug('User has access to the following managers for this project: %s',
                            [m['_id'] for m in managers])

        return managers.count() > 0
