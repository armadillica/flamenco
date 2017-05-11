"""Authorization management."""

import logging
import typing

import attr
import bson

import pillarsdk
from pillar import attrs_extra

# Roles required to view job, manager or task details.
ROLES_REQUIRED_TO_VIEW_ITEMS = {'demo', 'subscriber', 'admin', 'flamenco-admin'}
ROLES_REQUIRED_TO_VIEW_LOGS = {'admin', 'flamenco-admin'}


@attr.s
class Auth(object):
    """Handles authorization for Flamenco."""

    _log = attrs_extra.log('%s.Auth' % __name__)

    def current_user_is_flamenco_admin(self) -> bool:
        """Returns True iff the user is a Flamenco admin or regular admin."""

        from pillar.api.utils.authorization import user_matches_roles

        return user_matches_roles({'admin', 'flamenco-admin'})

    def current_user_is_flamenco_manager(self) -> bool:
        """Returns True iff the user is a Flamenco Manager."""

        from pillar.api.utils.authorization import user_matches_roles

        return user_matches_roles({'service', 'flamenco_manager'})

    def web_current_user_may_use_project(self,
                                         project: typing.Union[pillarsdk.Resource, dict]) -> bool:
        """Returns True iff the user is authorised to use Flamenco on the given project.

        This is linked to the Managers assigned to this project. As a result, you cannot
        use Flamenco until one or more Managers is assigned.
        """

        import pillar.auth
        from flamenco import current_flamenco

        user = pillar.auth.current_web_user
        if user.is_anonymous:
            self._log.debug('Anonymous user never has access to Flamenco.')
            return False

        # TODO Sybren: possibly split this up into a manager-fetching func + authorisation func.
        project_oid = bson.ObjectId(project['_id'])
        project_group_id = bson.ObjectId(project['permissions']['groups'][0]['group'])

        if str(project_group_id) not in user.groups:
            self._log.debug('User %s has no access to project %s.',
                            user.objectid, project_group_id)
            return False

        if 'flamenco-admin' in user.roles:
            self._log.debug('User is flamenco-admin, so has access to all Managers')
            return True

        managers_coll = current_flamenco.db('managers')
        managers = managers_coll.find({'projects': project_oid})

        if self._log.isEnabledFor(logging.DEBUG):
            self._log.debug('User has access to the following managers for this project: %s',
                            [m['_id'] for m in managers])

        return managers.count() > 0
