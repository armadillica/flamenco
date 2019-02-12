"""Task management."""
import collections
import datetime
import pathlib
import typing

import attr

import bson
from flask import current_app
import pymongo.collection
import werkzeug.exceptions as wz_exceptions

from pillar import attrs_extra
from pillar.api.file_storage_backends.abstract import FileType, Blob
from pillar.web.system_util import pillar_api
import pillar.api.projects.utils

from pillarsdk.exceptions import ResourceNotFound

# Keep this synced with _config.sass
COLOR_FOR_TASK_STATUS = collections.defaultdict(
    lambda: '#ccd',
    {
        'queued': '#b4bbaa',
        'canceled': '#999',
        'cancel-requested': '#d0a46d',
        'failed': '#ff8080',
        'fail-requested': '#bc8585',
        'claimed-by-manager': '#d1c5d3',
        'processing': '#ffbe00',
        'active': '#00ceff',
        'completed': '#bbe151',
        'paused': '#ccc',
    })

REQUEABLE_TASK_STATES = {'completed', 'canceled', 'failed'}
CANCELABLE_TASK_STATES = {'queued', 'claimed-by-manager', 'active'}
FAILED_TASK_STATES = {'canceled', 'failed'}
QUEUED_TASK_STATES = {'queued', 'claimed-by-manager'}
LOG_UPLOAD_REQUESTABLE_TASK_STATES = {'canceled', 'cancel-requested', 'failed', 'completed',
                                      'claimed-by-manager', 'fail-requested'}


@attr.s
class TaskManager(object):
    _log = attrs_extra.log('%s.TaskManager' % __name__)

    def collection(self) -> pymongo.collection.Collection:
        """Returns the Mongo database collection."""
        from flamenco import current_flamenco

        return current_flamenco.db('tasks')

    def api_create_task(self, job, commands, name, parents=None, priority=50,
                        status='queued', *, task_type: str) -> bson.ObjectId:
        """Creates a task in MongoDB for the given job, executing commands.

        Returns the ObjectId of the created task.
        """

        task = {
            'job': job['_id'],
            'manager': job['manager'],
            'user': job['user'],
            'name': name,
            'status': status,
            'job_type': job['job_type'],
            'task_type': task_type,
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

        r, _, _, status = current_app.post_internal('flamenco_tasks', task)
        if status != 201:
            self._log.error('Error %i creating task %s: %s',
                            status, task, r)
            raise wz_exceptions.InternalServerError('Unable to create task')

        return r['_id']

    def tasks_for_job(self, job_id, status=None, *,
                      page=1, max_results=250,
                      extra_where: dict = None):
        from .sdk import Task

        api = pillar_api()

        where = {'job': str(job_id)}
        if extra_where:
            where.update(extra_where)

        payload = {
            'where': where,
            'sort': [
                ('priority', -1),
                ('_id', 1),
            ],
            'max_results': max_results,
            'page': page,
        }
        if status:
            payload['where']['status'] = status

        tasks = Task.all(payload, api=api)
        self._log.debug(
            'task_for_job: where=%s  -> %i tasks in total, fetched page %i (%i per page)',
            payload['where'], tasks['_meta']['total'], page, max_results)
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

    def api_set_task_status_for_job(self, job_id: bson.ObjectId, from_status: str, to_status: str,
                                    *, now: datetime.datetime = None):
        """Updates the task status for all tasks of a job that have a particular status."""

        self._log.info('Flipping all tasks of job %s from status %r to %r',
                       job_id, from_status, to_status)

        from flamenco import current_flamenco

        current_flamenco.update_status_q('tasks',
                                         {'job': job_id, 'status': from_status},
                                         to_status,
                                         now=now)

    def api_set_activity(self, task_query: dict, new_activity: str):
        """Updates the activity for all tasks that match the query."""

        import uuid
        from bson import tz_util

        update = {
            'activity': new_activity,
            '_etag': uuid.uuid4().hex,
            '_updated': datetime.datetime.now(tz=tz_util.utc),
        }

        tasks_coll = self.collection()
        tasks_coll.update_many(task_query, {'$set': update})

    def api_find_job_enders(self, job_id):
        """Returns a list of tasks that could be the last tasks of a job.

        In other words, returns all tasks that are not a parent of other tasks.

        :returns: list of task IDs
        :rtype: list
        """

        tasks_coll = self.collection()

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

    def api_delete_tasks_for_job(self, job_id: bson.ObjectId):
        """Deletes all tasks for a given job.

        NOTE: this breaks references in the task log database.
        """

        from pymongo.results import DeleteResult

        self._log.info('Deleting all tasks of job %s', job_id)
        tasks_coll = self.collection()
        delres: DeleteResult = tasks_coll.delete_many({'job': job_id})
        self._log.info('Deleted %i tasks of job %s', delres.deleted_count, job_id)

    def api_requeue_task_and_successors(self, task_id: bson.ObjectId):
        """Recursively re-queue a task and its successors on the job's depsgraph.

        Does not update the job status itself. This is the responsibility
        of the caller.
        """
        from flamenco import current_flamenco

        tasks_coll = self.collection()
        visited_tasks: typing.MutableSet[bson.ObjectId] = set()

        def visit_task(tid: bson.ObjectId, depth: int):
            if depth > 10000:
                raise ValueError('Infinite recursion detected')

            if tid in visited_tasks:
                return
            visited_tasks.add(tid)

            current_flamenco.update_status('tasks', tid, 'queued')
            children = tasks_coll.find({'parents': tid}, projection={'_id': True})
            for child in children:
                visit_task(child['_id'], depth + 1)

        visit_task(task_id, 0)

    def _tasklog_blob_fname(self, task: dict) -> str:
        """Construct the blob filename for this task's log file.

        The blob is supposed to go into the project's storage bucket,
        so it does not contain the project ID.

        Assumes the log will be gzip-compressed, and thus the returned
        filename ends in '.log.gz'.
        """

        return f'flamenco-task-logs/job-{task["job"]}/task-{task["_id"]}.log.gz'

    def logfile_blob(self, task: dict) -> Blob:
        """Return the storage blob for this task's log file."""

        project_id = task['project']
        blob_fname = self._tasklog_blob_fname(task)
        bucket = pillar.api.projects.utils.storage(project_id)
        return bucket.blob(blob_fname)

    def api_attach_log(self, task: dict, file_obj: FileType) -> bool:
        """Store the POSTed task log as a file in the storage backend.

        Also updates the task itself to have a reference to the file.

        :return: Whether this file was new (False) or overwrote a pre-existing
            log file (True).
        """
        blob = self.logfile_blob(task)

        self._log.debug('Storing log for task %s in storage blob %s of project %s',
                        task['_id'], blob.name, task['project'])

        preexisting = blob.exists()
        blob.create_from_file(file_obj, content_type='application/gzip')
        blob.update_filename(pathlib.PurePosixPath(blob.name).name,
                             is_attachment=False)
        blob.update_content_type('text/plain', 'gzip')

        self._log.info('Stored log for task %s in storage blob %s of project %s',
                       task['_id'], blob.name, task['project'])

        tasks_coll = self.collection()
        tasks_coll.update_one({'_id': task['_id']}, {'$set': {
            'log_file': {
                'backend': blob.bucket.backend_name,
                'file_path': blob.name,
            },
        }})

        return preexisting


def setup_app(app):
    from . import eve_hooks, patch

    eve_hooks.setup_app(app)
    patch.setup_app(app)
