"""Manager management."""

import datetime
import enum
import logging
import typing

import attr
import bson
import pymongo.cursor

import werkzeug.exceptions as wz_exceptions

from pillar import attrs_extra, current_app
from pillar.api.utils.authentication import current_user_id

from flamenco import current_flamenco


@attr.s
class AuthTokenInfo:
    token = attr.ib(validator=attr.validators.instance_of(str))
    expire_time = attr.ib(validator=attr.validators.instance_of(datetime.datetime))


class ShareAction(enum.Enum):
    share = 'share'
    unshare = 'unshare'


@attr.s
class ManagerManager(object):
    """Manager manager.

    Performs actions on a Flamenco Manager. Does *NOT* test user permissions -- the caller
    is responsible for that.
    """

    _log = attrs_extra.log('%s.ManagerManager' % __name__)
    ShareAction = ShareAction  # so you can use current_flamenco.manager_manager.ShareAction

    def create_new_manager(self, name: str, description: str, owner_id: bson.ObjectId) \
            -> typing.Tuple[dict, dict, dict]:
        """Creates a new Manager, including its system account."""

        assert isinstance(owner_id, bson.ObjectId)

        from pillar.api import service
        from pillar.api.users import add_user_to_group

        # Create the service account and the Manager.
        account, token_data = service.create_service_account(
            '',
            ['flamenco_manager'],
            {'flamenco_manager': {}}
        )
        mngr_doc = self.create_manager_doc(account['_id'], name, description)

        # Assign the owner to the owner group.
        add_user_to_group(owner_id, mngr_doc['owner'])

        return account, mngr_doc, token_data

    def create_manager_doc(self, service_account_id, name, description, url=None):
        """Creates a new Flamenco manager and its owner group.

        Returns the MongoDB document.
        """

        from pillar.api.utils import str2id
        import bson

        # Determine the Object IDs beforehand, so that the manager can refer to the
        # group (by actual ID) and the group can mention the manager ID in the name.
        manager_id = bson.ObjectId()
        group_id = bson.ObjectId()

        # Create an owner group for this manager.
        group_doc = {
            '_id': group_id,
            'name': f'Owners of Flamenco Manager {manager_id}'
        }
        r, _, _, status = current_app.post_internal('groups', group_doc)
        if status != 201:
            self._log.error('Error creating manager owner group; status should be 201, not %i: %s',
                            status, r)
            raise ValueError(f'Unable to create Flamenco manager, status code {status}')

        # Create the manager.
        mngr_doc = {
            '_id': manager_id,
            'name': name,
            'description': description,
            'job_types': {
                'sleep': {
                    'vars': {}
                }
            },
            'service_account': str2id(service_account_id),
            'owner': group_id,
        }
        if url:
            mngr_doc['url'] = url
            self._log.info('Creating manager %r at %s', name, url)
        else:
            self._log.info('Creating manager %r', name)

        r, _, _, status = current_app.post_internal('flamenco_managers', mngr_doc)
        if status != 201:
            self._log.error('Status should be 201, not %i: %s' % (status, r))
            raise ValueError('Unable to create Flamenco manager, status code %i' % status)

        mngr_doc.update(r)
        return mngr_doc

    def user_is_manager(self) -> bool:
        """Returns True iff the current user is a Flamenco manager service account."""

        from pillar.api.utils.authorization import user_matches_roles

        return user_matches_roles(require_roles={'service', 'flamenco_manager'},
                                  require_all=True)

    def _get_manager(self,
                     mngr_doc_id: bson.ObjectId = None,
                     mngr_doc: dict = None,
                     projection: dict = None) -> typing.Tuple[bson.ObjectId, dict]:

        assert (mngr_doc_id is None) != (mngr_doc is None), \
            'Either one or the other parameter must be given.'

        if mngr_doc is None:
            mngr_coll = current_flamenco.db('managers')
            mngr_doc = mngr_coll.find_one({'_id': mngr_doc_id}, projection)
            if not mngr_doc:
                self._log.warning('user_manages(%s): no such document (user=%s)',
                                  mngr_doc_id, current_user_id())
                raise ValueError(f'Manager {mngr_doc_id} does not exist.')
        else:
            mngr_doc_id = mngr_doc['_id']

        return mngr_doc_id, mngr_doc

    def user_is_owner(self, *, mngr_doc_id: bson.ObjectId = None, mngr_doc: dict = None) -> bool:
        """Returns True iff the current user is an owner of the given Flamenco Manager."""

        import flask
        from pillar.api.utils.authorization import user_matches_roles
        from flamenco.auth import ROLES_REQUIRED_TO_VIEW_FLAMENCO, ROLES_REQUIRED_TO_USE_FLAMENCO

        current_user = flask.g.get('current_user') or {}
        user_id = current_user.get('user_id')

        if not user_id or not user_matches_roles(ROLES_REQUIRED_TO_VIEW_FLAMENCO):
            self._log.debug('user_is_owner(...): user %s is not a subscriber/demo', user_id)
            return False

        if not user_matches_roles(ROLES_REQUIRED_TO_USE_FLAMENCO):
            self._log.debug('user_is_owner(...): user %s is not in %s',
                            user_id, ROLES_REQUIRED_TO_USE_FLAMENCO)
            return False

        mngr_doc_id, mngr_doc = self._get_manager(mngr_doc_id, mngr_doc, {'owner': 1})

        owner_group = mngr_doc.get('owner')
        if not owner_group:
            self._log.warning('user_is_owner(%s): Manager has no owner!', mngr_doc_id)
            return False

        user_groups = current_user.get('groups', set())
        return owner_group in user_groups

    def user_manages(self, *, mngr_doc_id: bson.ObjectId = None, mngr_doc: dict = None) -> bool:
        """
        Returns True iff the current user is the Flamenco manager service account for this doc.
        """

        if not self.user_is_manager():
            self._log.debug('user_manages(...): user %s is not a Flamenco manager service account',
                            current_user_id())
            return False

        mngr_doc_id, mngr_doc = self._get_manager(mngr_doc_id, mngr_doc, {'service_account': 1})

        service_account = mngr_doc.get('service_account')
        user_id = current_user_id()
        if service_account != user_id:
            self._log.debug('user_manages(%s): current user %s is not manager %s',
                            mngr_doc_id, user_id, service_account)
            return False

        return True

    def user_may_use(self, *, mngr_doc_id: bson.ObjectId = None, mngr_doc: dict = None) -> bool:
        """Returns True iff this user may use this Flamenco Manager.

        Usage implies things like requeuing tasks and jobs, creating new jobs, etc.
        """

        import flask
        from pillar.api.utils.authorization import user_matches_roles
        from flamenco import current_flamenco
        from ..auth import ROLES_REQUIRED_TO_USE_FLAMENCO

        # Flamenco Admins always have access.
        if current_flamenco.auth.current_user_is_flamenco_admin():
            return True

        mngr_doc_id, mngr_doc = self._get_manager(mngr_doc_id, mngr_doc, {'user_groups': 1})

        current_user = flask.g.get('current_user', {})
        user_groups = set(current_user.get('groups', []))

        owner_group = mngr_doc.get('owner')
        if owner_group and owner_group in user_groups:
            return True

        if not user_matches_roles(ROLES_REQUIRED_TO_USE_FLAMENCO):
            return False

        manager_groups = set(mngr_doc.get('user_groups', []))
        return bool(user_groups.intersection(manager_groups))

    def api_assign_to_project(self,
                              manager_id: bson.ObjectId,
                              project_id: bson.ObjectId,
                              action: str) -> bool:
        """Assigns the manager to the given project.

        Does NOT check whether the project actually exists or not.

        :param action: either 'assign' or 'remove'
        :returns: True iff the action was successful.
        """

        from collections import defaultdict
        from pymongo.results import UpdateResult
        from flamenco import current_flamenco
        from pillar.api.projects import utils as project_utils

        if action not in {'assign', 'remove'}:
            raise ValueError("Action must be either 'assign' or 'remove'")

        assert isinstance(manager_id, bson.ObjectId)
        assert isinstance(project_id, bson.ObjectId)

        mngr_coll = current_flamenco.db('managers')
        manager_doc = mngr_coll.find_one({'_id': manager_id},
                                         {'projects': 1,
                                          'user_groups': 1})

        if not manager_doc:
            self._log.warning('api_assign_to_project(%s, %s): no manager with id=%s (user=%s)',
                              manager_id, project_id, manager_id, current_user_id())
            return False

        mngr_projects = set(manager_doc.get('projects', []))
        mngr_user_groups = set(manager_doc.get('user_groups', []))

        admin_group_id = project_utils.get_admin_group_id(project_id)

        if action == 'assign':
            mngr_projects.add(project_id)
            mngr_user_groups.add(admin_group_id)
        else:
            mngr_projects.discard(project_id)
            mngr_user_groups.discard(admin_group_id)

        # Convert to list because JSON/BSON doesn't do sets, and sort to get predictable output.
        projects = sorted(mngr_projects)
        user_groups = sorted(mngr_user_groups)

        if self._log.isEnabledFor(logging.INFO):
            self._log.info(
                'Updating Manager %s projects to [%s] and user_groups to [%s]',
                manager_id,
                ', '.join(f"'{pid}'" for pid in projects),
                ', '.join(f"'{gid}'" for gid in user_groups),
            )

        update = defaultdict(dict)
        if projects:
            update['$set']['projects'] = projects
        else:
            update['$unset']['projects'] = 1

        if user_groups:
            update['$set']['user_groups'] = user_groups
        else:
            update['$unset']['user_groups'] = 1

        res: UpdateResult = mngr_coll.update_one({'_id': manager_id}, update)

        if res.matched_count < 1:
            self._log.error('Unable to update projects on Manager %s to %s: %s',
                            manager_id,
                            ', '.join(f"'{pid}'" for pid in projects),
                            res)
            return False
        return True

    def find_service_account_id(self, manager_id: bson.ObjectId) -> bson.ObjectId:
        _, manager = self._get_manager(mngr_doc_id=manager_id,
                                       projection={'service_account': 1})
        users_coll = current_app.db('users')
        service_account_id = manager['service_account']
        service_account = users_coll.find_one({'_id': service_account_id,
                                               'service.flamenco_manager': {'$exists': True}})
        if not service_account:
            self._log.error('Unable to find service account %s for manager %s',
                            service_account_id, manager_id)
            raise wz_exceptions.NotFound()
        return service_account_id

    def auth_token(self, manager_id: bson.ObjectId) -> typing.Optional[AuthTokenInfo]:
        """Returns the authentication token info of the given Manager."""

        service_account_id = self.find_service_account_id(manager_id)

        tokens_coll = current_app.db('tokens')
        tokens = tokens_coll.find({'user': service_account_id})
        if tokens.count() == 0:
            self._log.warning('Manager %s with service account %s has no authentication token',
                              manager_id, service_account_id)
            return None

        if tokens.count() > 1:
            self._log.warning('Manager %s with service account %s has %i authentication tokens',
                              manager_id, service_account_id, tokens.count())

        token = tokens.next()
        return AuthTokenInfo(
            token=token['token'],
            expire_time=token['expire_time'],
        )

    def gen_new_auth_token(self, manager_id: bson.ObjectId) -> typing.Optional[AuthTokenInfo]:
        """Generates a new authentication token for the given Manager.

        Deletes all pre-existing authentication tokens of the Manager.
        """

        from pillar.api import service
        import pymongo.results

        self._log.info('Generating new authentication token for Manager %s on behalf of user %s',
                       manager_id, current_user_id())

        service_account_id = self.find_service_account_id(manager_id)

        tokens_coll = current_app.db('tokens')
        result: pymongo.results.DeleteResult = tokens_coll.delete_many({'user': service_account_id})
        self._log.debug('Deleted %i authentication tokens of Manager %s',
                        result.deleted_count, manager_id)

        token = service.generate_auth_token(service_account_id)
        return AuthTokenInfo(
            token=token['token'],
            expire_time=token['expire_time'],
        )

    def share_unshare_manager(self, manager_id: bson.ObjectId, share_action: ShareAction,
                              subject_uid: bson.ObjectId):
        self._log.info('%s Manager %s on behalf of user %s, subject user is %s',
                       share_action, manager_id, current_user_id(), subject_uid)

        from pillar.api import users

        _, manager = self._get_manager(mngr_doc_id=manager_id)
        owner_gid = manager['owner']

        # Check that there is at least one user left in the group.
        users_coll = current_app.db('users')
        owners = users_coll.find({'groups': owner_gid})
        if share_action == ShareAction.unshare and owners.count() < 2:
            self._log.warning('User %s tried to make Manager %s ownerless',
                              current_user_id(), manager_id)
            raise ValueError('Manager cannot become ownerless.')

        group_action = {
            ShareAction.share: '$addToSet',
            ShareAction.unshare: '$pull',
        }[share_action]

        users.user_group_action(subject_uid, owner_gid, group_action)

    def owning_users(self, owner_gid: bson.ObjectId) -> typing.List[dict]:
        assert isinstance(owner_gid, bson.ObjectId)

        users_coll = current_app.db('users')
        users = users_coll.find({'groups': owner_gid})
        return list(users)

    def managers_for_project(self, project_id: bson.ObjectId) -> typing.List[bson.ObjectId]:
        """Returns a list of Manager object IDs assigned to the given project."""

        assert isinstance(project_id, bson.ObjectId)

        managers_coll = current_flamenco.db('managers')
        managers = managers_coll.find({'projects': project_id}, {'_id': 1})
        return [m['_id'] for m in managers]

    def owned_managers(self, user_group_ids: typing.List[bson.ObjectId]) -> pymongo.cursor.Cursor:
        """Returns a Mongo cursor of Manager object IDs owned by the given user."""

        managers_coll = current_flamenco.db('managers')
        managers = managers_coll.find({'owner': {'$in': user_group_ids}}, {'_id': 1})
        return managers


def setup_app(app):
    from . import eve_hooks, api, patch

    eve_hooks.setup_app(app)
    api.setup_app(app)
    patch.setup_app(app)
