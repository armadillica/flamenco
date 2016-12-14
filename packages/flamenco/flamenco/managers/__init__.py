"""Manager management."""

import attr

from pillar import attrs_extra
from pillar.web.system_util import pillar_api

from pillarsdk.resource import List
from pillarsdk.resource import Find
from pillarsdk.resource import Create
from pillarsdk.resource import Post
from pillarsdk.resource import Update
from pillarsdk.resource import Delete
from pillarsdk.resource import Replace
from pillarsdk.exceptions import ResourceNotFound


class Manager(List, Find, Create, Post, Update, Delete, Replace):
    """Manager class wrapping the REST nodes endpoint"""
    path = 'flamenco/managers'


@attr.s
class ManagerManager(object):
    _log = attrs_extra.log('%s.ManagerManager' % __name__)

    def create_manager(self, name, description, url=None):
        """Creates a new Flamenco manager.

        Returns the MongoDB document.
        """

        from eve.methods.post import post_internal

        mngr_doc = {
            'name': name,
            'description': description,
            'job_types': {
                'sleep': {
                    'vars': {}
                }
            },
        }
        if url:
            mngr_doc['url'] = url
            self._log.info('Creating manager %r at %s', name, url)
        else:
            self._log.info('Creating manager %r', name)

        r, _, _, status = post_internal('flamenco.managers', mngr_doc)
        if status != 201:
            self._log.error('Status should be 201, not %i: %s' % (status, r))
            raise ValueError('Unable to create Flamenco manager, status code %i' % status)

        mngr_doc.update(r)
        return mngr_doc
