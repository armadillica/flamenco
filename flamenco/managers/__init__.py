"""Manager management."""

import logging
import typing

import attr
import bson

from pillar import attrs_extra

from pillarsdk.resource import List
from pillarsdk.resource import Find
from pillarsdk.resource import Create
from pillarsdk.resource import Post
from pillarsdk.resource import Update
from pillarsdk.resource import Delete
from pillarsdk.resource import Replace


class Manager(List, Find, Create, Post, Update, Delete, Replace):
    """Manager class wrapping the REST nodes endpoint"""
    path = 'flamenco/managers'


@attr.s
class ManagerManager(object):
    """Manager manager.

    Performs actions on a Flamenco Manager. Does *NOT* test user permissions -- the caller
    is responsible for that.
    """

    _log = attrs_extra.log('%s.ManagerManager' % __name__)

    def create_manager(self, service_account_id, name, description, url=None):
        """Creates a new Flamenco manager.

        Returns the MongoDB document.
        """

        from eve.methods.post import post_internal
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
        r, _, _, status = post_internal('groups', group_doc)
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

        r, _, _, status = post_internal('flamenco_managers', mngr_doc)
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
                     projection: dict=None) -> typing.Tuple[bson.ObjectId, dict]:

        assert (mngr_doc_id is None) != (mngr_doc is None), \
            'Either one or the other parameter must be given.'

        from pillar.api.utils.authentication import current_user_id
        from flamenco import current_flamenco

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
        from pillar.api.utils.authorization import user_has_role

        current_user = flask.g.get('current_user') or {}
        user_id = current_user.get('user_id')

        if not user_id or not user_has_role('subscriber', current_user):
            self._log.debug('user_is_owner(...): user %s is not a subscriber', user_id)
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

        from pillar.api.utils.authentication import current_user_id

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
        from flamenco import current_flamenco

        # Flamenco Admins always have access.
        if current_flamenco.current_user_is_flamenco_admin():
            return True

        mngr_doc_id, mngr_doc = self._get_manager(mngr_doc_id, mngr_doc, {'user_groups': 1})

        current_user = flask.g.get('current_user', {})
        user_groups = set(current_user.get('groups', []))
        manager_groups = set(mngr_doc.get('user_groups', []))

        return bool(user_groups.intersection(manager_groups))

    def api_assign_to_project(self,
                              manager_id: bson.ObjectId,
                              project_id: bson.ObjectId,
                              action: str) -> bool:
        """Assigns the manager to the given project.

        Does NOT check whether the project actually exists or not.

        :param action: either 'assign' or 'unassign'
        :returns: True iff the action was successful.
        """

        from collections import defaultdict
        from pymongo.results import UpdateResult
        from flamenco import current_flamenco
        from pillar.api.utils.authentication import current_user_id
        from pillar.api.projects import utils as project_utils

        if action not in {'assign', 'remove'}:
            raise ValueError("Action must be either 'assign' or 'remove'")

        mngr_coll = current_flamenco.db('managers')
        manager_doc = mngr_coll.find_one({'_id': manager_id},
                                         {'projects': 1,
                                          'user_groups': 1})

        if not manager_doc:
            self._log.warning('api_assign_to_project(%s): no such document (user=%s)',
                              manager_id, current_user_id())
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


def setup_app(app):
    from . import eve_hooks, api, patch

    eve_hooks.setup_app(app)
    api.setup_app(app)
    patch.setup_app(app)
