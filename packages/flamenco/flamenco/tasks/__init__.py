"""Task management."""

import attr

import pillarsdk
from pillar import attrs_extra
from pillar.web.system_util import pillar_api


@attr.s
class TaskManager(object):
    _log = attrs_extra.log('%s.TaskManager' % __name__)

    def delete_task(self, task_id, etag):
        api = pillar_api()
        self._log.info('Deleting task %s', task_id)
        task = pillarsdk.Resource({'_id': task_id, '_etag': etag})
        task.path = 'flamenco/tasks'
        task.delete(api=api)
