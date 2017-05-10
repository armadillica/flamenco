"""Authorization management."""

import attr

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
