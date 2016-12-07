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
