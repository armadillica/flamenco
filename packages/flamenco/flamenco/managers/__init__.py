"""Manager management."""

import attr

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
    _log = attrs_extra.log('%s.ManagerManager' % __name__)

    def create_manager(self, service_account_id, name, description, url=None):
        """Creates a new Flamenco manager.

        Returns the MongoDB document.
        """

        from eve.methods.post import post_internal
        from pillar.api.utils import str2id

        mngr_doc = {
            'name': name,
            'description': description,
            'job_types': {
                'sleep': {
                    'vars': {}
                }
            },
            'service_account': str2id(service_account_id),
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

    def user_is_manager(self):
        """Returns True iff the current user is a Flamenco manager service account."""

        from pillar.api.utils.authorization import user_matches_roles

        return user_matches_roles(require_roles={u'service', u'flamenco_manager'},
                                  require_all=True)

    def user_manages(self, mngr_doc_id=None, mngr_doc=None):
        """
        Returns True iff the current user is the Flamenco manager service account for this doc.
        """

        assert (mngr_doc_id is None) != (mngr_doc is None), \
            'Either one or the other parameter must be given.'

        from pillar.api.utils.authentication import current_user_id
        from flamenco import current_flamenco

        if not self.user_is_manager():
            self._log.debug('user_manages(...): user is not a Flamenco manager service account')
            return False

        if mngr_doc is None:
            mngr_coll = current_flamenco.db('managers')
            mngr_doc = mngr_coll.find_one({'_id': mngr_doc_id},
                                          {'service_account': 1})
            if not mngr_doc:
                self._log.debug('user_manages(%s): no such document', mngr_doc_id)
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


def setup_app(app):
    from . import eve_hooks, api

    eve_hooks.setup_app(app)
    api.setup_app(app)
