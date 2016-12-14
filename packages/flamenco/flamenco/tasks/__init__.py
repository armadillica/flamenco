"""Task management."""

import attr

import werkzeug.exceptions as wz_exceptions

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

    def api_create_task(self, job, commands, name, parents=None):
        """Creates a task in MongoDB for the given job, executing commands.

        Returns the ObjectId of the created task.
        """

        from eve.methods.post import post_internal

        task = {
            'job': job['_id'],
            'manager': job['manager'],
            'user': job['user'],
            'name': name,
            'status': 'queued',
            'job_type': job['job_type'],
            'commands': [cmd.to_dict() for cmd in commands],
            'priority': job['priority'],
        }
        # Insertion of None parents is not supported
        if parents:
            task['parents'] = parents

        self._log.info('Creating task %s for manager %s, user %s',
                       name, job['manager'], job['user'])

        r, _, _, status = post_internal('flamenco.tasks', task)
        if status != 201:
            self._log.error('Error %i creating task %s: %s',
                            status, task, r)
            raise wz_exceptions.InternalServerError('Unable to create task')

        return r['_id']

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
