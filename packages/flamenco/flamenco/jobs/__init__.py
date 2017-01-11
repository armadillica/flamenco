"""Job management."""

import collections
import copy

import attr
import pillarsdk
from pillar import attrs_extra
from pillar.web.system_util import pillar_api

from pillarsdk.resource import List
from pillarsdk.resource import Find
from pillarsdk.resource import Create
from pillarsdk.resource import Post
from pillarsdk.resource import Update
from pillarsdk.resource import Delete
from pillarsdk.resource import Replace

from flamenco import current_flamenco


class ProjectSummary(object):
    """Summary of the jobs in a project."""

    def __init__(self):
        self._counts = collections.defaultdict(int)
        self._total = 0

    def count(self, status):
        self._counts[status] += 1
        self._total += 1

    def percentages(self):
        """Generator, yields (status, percentage) tuples.

        The percentage is on a 0-100 scale.
        """

        remaining = 100
        last_index = len(self._counts) - 1

        for idx, status in enumerate(sorted(self._counts.keys())):
            if idx == last_index:
                yield (status, remaining)
                continue

            perc = float(self._counts[status]) / self._total
            whole_perc = int(round(perc * 100))
            remaining -= whole_perc

            yield (status, whole_perc)


class Job(List, Find, Create, Post, Update, Delete, Replace):
    """Job class wrapping the REST nodes endpoint
    """
    path = 'flamenco/jobs'
    ensure_query_projections = {'project': 1}


@attr.s
class JobManager(object):
    _log = attrs_extra.log('%s.JobManager' % __name__)

    def api_create_job(self, job_name, job_desc, job_type, job_settings,
                       project_id, user_id, manager_id, priority=50):
        """Creates a job, returning a dict with its generated fields."""

        from eve.methods.post import post_internal

        job = {
            'name': job_name,
            'description': job_desc,
            'job_type': job_type,
            'project': project_id,
            'user': user_id,
            'manager': manager_id,
            'status': 'queued',
            'priority': int(priority),
            'settings': copy.deepcopy(job_settings),
        }

        self._log.info('Creating job %r for user %s and manager %s',
                       job_name, user_id, manager_id)

        r, _, _, status = post_internal('flamenco_jobs', job)
        if status != 201:
            self._log.error('Status should be 201, not %i: %s' % (status, r))
            raise ValueError('Unable to create Flamenco job, status code %i' % status)

        job.update(r)
        return job

    def edit_job(self, job_id, **fields):
        """Edits a job.

        :type job_id: str
        :type fields: dict
        :rtype: pillarsdk.Node
        """

        api = pillar_api()
        job = pillarsdk.Node.find(job_id, api=api)

        job._etag = fields.pop('_etag')
        job.name = fields.pop('name')
        job.description = fields.pop('description')
        job.status = fields.pop('status')
        job.properties.job_type = fields.pop('job_type', '').strip() or None

        users = fields.pop('users', None)
        job.properties.assigned_to = {'users': users or []}

        self._log.info('Saving job %s', job.to_dict())

        if fields:
            self._log.warning('edit_job(%r, ...) called with unknown fields %r; ignoring them.',
                              job_id, fields)

        job.update(api=api)
        return job

    def delete_job(self, job_id, etag):
        api = pillar_api()

        self._log.info('Deleting job %s', job_id)
        job = pillarsdk.Resource({'_id': job_id, '_etag': etag})
        job.path = 'flamenco/jobs'
        job.delete(api=api)

    def jobs_for_user(self, user_id):
        """Returns the jobs for the given user.

        :returns: {'_items': [job, job, ...], '_meta': {Eve metadata}}
        """

        api = pillar_api()

        # TODO: also include jobs assigned to any of the user's groups.
        jobs = pillarsdk.resource.List()
        jobs.list_class.path = 'flamenco/jobs'
        j = jobs.all({
            'where': {
                'user': user_id,
            }
        }, api=api)

        return j

    def jobs_for_project(self, project_id):
        """Returns the jobs for the given project.

        :returns: {'_items': [job, job, ...], '_meta': {Eve metadata}}
        """

        api = pillar_api()
        jobs = pillarsdk.resource.List()
        jobs.list_class.path = 'flamenco/jobs'
        j = jobs.all({
            'where': {
                'project': project_id,
            }}, api=api)
        return j

    def job_status_summary(self, project_id):
        """Returns number of shots per shot status for the given project.

                :rtype: ProjectSummary
                """

        api = pillar_api()

        # TODO: turn this into an aggregation call to do the counting on
        # MongoDB.
        jobs = Job.all({
            'where': {
                'project': project_id,
            },
            'projection': {
                'status': 1,
            },
            'order': [
                ('status', 1),
            ],
        }, api=api)

        # FIXME: this breaks when we hit the pagination limit.
        summary = ProjectSummary()
        for job in jobs['_items']:
            summary.count(job['status'])

        return summary

    def update_job_after_task_status_change(self, job_id, task_id, new_task_status):
        """Updates the job status based on the status of this task and other tasks in the job.
        """

        if new_task_status == {'queued', 'cancel-requested'}:
            # Ignore; for now re-queueing a task doesn't change the job status.
            # Also, canceling a single task has no influence on the job itself.
            return

        if new_task_status == 'canceled':
            # This could be the last cancel-requested task to go to 'canceled.
            tasks_coll = current_flamenco.db('tasks')
            statuses = tasks_coll.distinct('status', {'job': job_id})
            if 'cancel-requested' not in statuses:
                self._log.info('Last task %s of job %s went from cancel-requested to canceld.',
                               task_id, job_id)
                self.set_job_status(job_id, 'canceled')
            return

        if new_task_status == 'failed':
            self._log.warning('Failing job %s because one of its tasks %s failed',
                              job_id, task_id)
            self.set_job_status(job_id, 'failed')
            return

        if new_task_status in {'claimed-by-manager', 'active', 'processing'}:
            self._log.info('Job %s became active because one of its tasks %s changed status to %s',
                           job_id, task_id, new_task_status)
            self.set_job_status(job_id, 'active')
            return

        if new_task_status == 'completed':
            # Maybe all tasks are completed, which should complete the job.
            tasks_coll = current_flamenco.db('tasks')
            statuses = tasks_coll.distinct('status', {'job': job_id})
            if statuses == ['completed']:
                self._log.info('All tasks (last one was %s) of job %s are completed, '
                               'setting job to completed.',
                               task_id, job_id)
                self.set_job_status(job_id, 'completed')
            return

        self._log.warning('Task %s of job %s obtained status %s, '
                          'which we do not know how to handle.',
                          task_id, job_id, new_task_status)

    def set_job_status(self, job_id, new_status):
        """Updates the job status."""

        jobs_coll = current_flamenco.db('jobs')
        curr_job = jobs_coll.find_one({'_id': job_id}, projection={'status': 1})
        old_status = curr_job['status']

        current_flamenco.update_status('jobs', job_id, new_status)
        self.handle_job_status_change(job_id, old_status, new_status)

    def handle_job_status_change(self, job_id, old_status, new_status):
        """Updates task statuses based on this job status transition."""

        query = None
        to_status = None
        if new_status in {'completed', 'canceled'}:
            # Nothing to do; this will happen as a response to all tasks receiving this status.
            pass
        elif new_status == 'active':
            # Nothing to do; this happens when a task gets started, which has nothing to
            # do with other tasks in the job.
            pass
        elif new_status in {'cancel-requested', 'failed'}:
            # Request cancel of any task that might run on the manager.
            current_flamenco.update_status_q(
                'tasks',
                {'job': job_id, 'status': {'$in': ['active', 'claimed-by-manager']}},
                'cancel-requested')
            # Directly cancel any task that might run in the future, but is not touched by
            # a manager yet.
            current_flamenco.update_status_q(
                'tasks',
                {'job': job_id, 'status': 'queued'},
                'canceled')
            return
        elif new_status == 'queued':
            if old_status == 'completed':
                # Re-queue all tasks except cancel-requested; those should remain
                # untouched; changing their status is only allowed by managers, to avoid
                # race conditions.
                query = {'status': {'$ne': 'cancel-requested'}}
            else:
                # Re-queue any non-completed task. Cancel-requested tasks should also be
                # untouched; changing their status is only allowed by managers, to avoid
                # race conditions.
                query = {'status': {'$nin': ['completed', 'cancel-requested']}}
            to_status = 'queued'

        if query is None:
            self._log.debug('Job %s status change from %s to %s has no effect on tasks.',
                            job_id, old_status, new_status)
            return
        if to_status is None:
            self._log.error('Job %s status change from %s to %s has to_status=None, aborting.',
                            job_id, old_status, new_status)
            return

        # Update the tasks.
        query['job'] = job_id

        current_flamenco.update_status_q('tasks', query, to_status)


def setup_app(app):
    from . import eve_hooks

    eve_hooks.setup_app(app)
