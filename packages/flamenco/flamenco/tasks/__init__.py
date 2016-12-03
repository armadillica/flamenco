"""Task management."""

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


class Task(List, Find, Create, Post, Update, Delete, Replace):
    """Job class wrapping the REST nodes endpoint
    """
    path = 'flamenco/tasks'
    ensure_query_projections = {'project': 1, 'job': 1}


@attr.s
class TaskManager(object):
    _log = attrs_extra.log('%s.TaskManager' % __name__)

    def tasks_for_job(self, job_id, status=None, page=1):
        self._log.info('Fetching task for job %s', job_id)
        api = pillar_api()
        payload = {
            'where': {
                'job': job_id,
            }}
        if status:
            payload['where']['status'] = status
        tasks = Task.all(payload, api=api)
        return tasks

    def tasks_for_user(self, user_id, status=None, page=1):
        self._log.info('Fetching task for user %s', user_id)
        api = pillar_api()
        payload = {
            'where': {
                'user': user_id,
            }}
        if status:
            payload['where']['status'] = status
        tasks = Task.all(payload, api=api)
        return tasks

    def tasks_for_project(self, project_id):
        """Returns the tasks for the given project.

        :returns: {'_items': [task, task, ...], '_meta': {Eve metadata}}
        """

        api = pillar_api()
        tasks = Task.all({
            'where': {
                'project': project_id,
            }}, api=api)
        return tasks
