"""Task management."""

import attr

import werkzeug.exceptions as wz_exceptions

from pillar import attrs_extra
from pillar.web.system_util import pillar_api

from pillarsdk.exceptions import ResourceNotFound

# Keep this synced with _config.sass
COLOR_FOR_TASK_STATUS = {
    'queued': '#b4bbaa',
    'canceled': '#999',
    'failed': '#ff8080',
    'claimed-by-manager': '#d1c5d3',
    'processing': '#ffbe00',
    'active': '#00ceff',
    'completed': '#bbe151',
}

REQUEABLE_TASK_STATES = {'completed', 'canceled', 'failed'}


@attr.s
class TaskManager(object):
    _log = attrs_extra.log('%s.TaskManager' % __name__)

    def api_create_task(self, job, commands, name, parents=None, priority=50):
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
            'job_priority': job['priority'],
            'priority': priority,
            'project': job['project'],
        }
        # Insertion of None parents is not supported
        if parents:
            task['parents'] = parents

        self._log.info('Creating task %s for manager %s, user %s',
                       name, job['manager'], job['user'])

        r, _, _, status = post_internal('flamenco_tasks', task)
        if status != 201:
            self._log.error('Error %i creating task %s: %s',
                            status, task, r)
            raise wz_exceptions.InternalServerError('Unable to create task')

        return r['_id']

    def tasks_for_job(self, job_id, status=None, page=1):
        from .sdk import Task

        api = pillar_api()
        payload = {
            'where': {
                'job': unicode(job_id),
            },
            'sorted': [
                ('priority', -1),
                ('_id', 1),
            ],
        }
        if status:
            payload['where']['status'] = status
        tasks = Task.all(payload, api=api)
        return tasks

    def tasks_for_project(self, project_id):
        """Returns the tasks for the given project.

        :returns: {'_items': [task, task, ...], '_meta': {Eve metadata}}
        """
        from .sdk import Task

        api = pillar_api()
        try:
            tasks = Task.all({
                'where': {
                    'project': project_id,
                }}, api=api)
        except ResourceNotFound:
            return {'_items': [], '_meta': {'total': 0}}

        return tasks

    def web_set_task_status(self, task_id, new_status):
        """Web-level call to updates the task status."""
        from .sdk import Task

        api = pillar_api()
        task = Task({'_id': task_id})
        task.patch({'op': 'set-task-status',
                    'status': new_status}, api=api)

    def api_find_job_enders(self, job_id):
        """Returns a list of tasks that could be the last tasks of a job.

        In other words, returns all tasks that are not a parent of other tasks.

        :returns: list of task IDs
        :rtype: list
        """

        from flamenco import current_flamenco

        tasks_coll = current_flamenco.db('tasks')

        # Get the distinct set of tasks used as parents.
        parent_tasks = tasks_coll.aggregate([
            {'$match': {'job': job_id}},
            {'$project': {'parents': 1}},
            {'$unwind': {'path': '$parents'}},
            {'$group': {'_id': '$parents'}},
        ])
        parent_ids = [t['_id'] for t in parent_tasks]

        # Get all the tasks that do not have such an ID.
        tasks = tasks_coll.find({'job': job_id,
                                 '_id': {'$nin': parent_ids}},
                                projection={'_id': 1})

        tids = [t['_id'] for t in tasks]
        return tids


def setup_app(app):
    from . import eve_hooks, patch

    eve_hooks.setup_app(app)
    patch.setup_app(app)
