"""Manager management."""

import logging

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

    def user_is_owner(self, mngr_doc_id: bson.ObjectId = None, mngr_doc: dict = None) -> bool:
        """Returns True iff the current user is an owner of the given Flamenco Manager."""

        assert (mngr_doc_id is None) != (mngr_doc is None), \
            'Either one or the other parameter must be given.'

        import flask
        from pillar.api.utils.authorization import user_has_role
        from flamenco import current_flamenco

        current_user = flask.g.get('current_user') or {}
        user_id = current_user.get('user_id')

        if not user_id or not user_has_role('subscriber', current_user):
            self._log.debug('user_is_owner(...): user %s is not a subscriber', user_id)
            return False

        if mngr_doc is None:
            mngr_coll = current_flamenco.db('managers')
            mngr_doc = mngr_coll.find_one({'_id': mngr_doc_id},
                                          {'owner': 1})
            if not mngr_doc:
                self._log.warning('user_is_owner(%s): no such document', mngr_doc_id)
                return False
        else:
            mngr_doc_id = mngr_doc['_id']

        owner_group = mngr_doc.get('owner')
        if not owner_group:
            self._log.warning('user_is_owner(%s): Manager has no owner!', mngr_doc_id)
            return False

        user_groups = current_user.get('groups', set())
        return owner_group in user_groups

    def user_manages(self, mngr_doc_id: bson.ObjectId = None, mngr_doc: dict = None) -> bool:
        """
        Returns True iff the current user is the Flamenco manager service account for this doc.
        """

        assert (mngr_doc_id is None) != (mngr_doc is None), \
            'Either one or the other parameter must be given.'

        from pillar.api.utils.authentication import current_user_id
        from flamenco import current_flamenco

        if not self.user_is_manager():
            self._log.debug('user_manages(...): user %s is not a Flamenco manager service account',
                            current_user_id())
            return False

        if mngr_doc is None:
            mngr_coll = current_flamenco.db('managers')
            mngr_doc = mngr_coll.find_one({'_id': mngr_doc_id},
                                          {'service_account': 1})
            if not mngr_doc:
                self._log.warning('user_manages(%s): no such document (user=%s)',
                                  mngr_doc_id, current_user_id())
                return False
        else:
            mngr_doc_id = mngr_doc['_id']

        service_account = mngr_doc.get('service_account')
        user_id = current_user_id()
        if service_account != user_id:
            self._log.debug('user_manages(%s): current user %s is not manager %s',
                            mngr_doc_id, user_id, service_account)
            return False

        return True

    def api_assign_to_project(self,
                              manager_id: bson.ObjectId,
                              project_id: bson.ObjectId,
                              action: str) -> bool:
        """Assigns the manager to the given project.

        Does NOT check whether the project actually exists or not.

        :param action: either 'assign' or 'unassign'
        :returns: True iff the action was successful.
        """

        from pymongo.results import UpdateResult
        from flamenco import current_flamenco
        from pillar.api.utils.authentication import current_user_id

        if action not in {'assign', 'remove'}:
            raise ValueError("Action must be either 'assign' or 'remove'")

        mngr_coll = current_flamenco.db('managers')
        manager_doc = mngr_coll.find_one({'_id': manager_id},
                                         {'projects': 1})

        if not manager_doc:
            self._log.warning('api_assign_to_project(%s): no such document (user=%s)',
                              manager_id, current_user_id())
            return False

        mngr_projects = set(manager_doc.get('projects', []))
        is_assigned = project_id in mngr_projects
        if is_assigned == (action == 'assign'):
            self._log.debug('api_assign_to_project(%s, %s, %s): this is a no-op.',
                            manager_id, project_id, action)
            return True

        if action == 'assign':
            mngr_projects.add(project_id)
        else:
            mngr_projects.discard(project_id)

        # Convert to list because JSON/BSON doesn't do sets, and sort to get predictable output.
        projects = sorted(mngr_projects)

        if self._log.isEnabledFor(logging.INFO):
            self._log.info('Updating Manager %s projects to [%s]', manager_id,
                           ', '.join(f"'{pid}'" for pid in projects))

        if projects:
            update = {'$set': {'projects': projects}}
        else:
            update = {'$unset': {'projects': 1}}
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
