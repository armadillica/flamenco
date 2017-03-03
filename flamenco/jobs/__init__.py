"""Job management."""

import collections
import copy

import attr

import pillarsdk
from pillar import attrs_extra
from pillar.web.system_util import pillar_api

from flamenco import current_flamenco

CANCELABLE_JOB_STATES = {'active', 'queued', 'failed'}
REQUEABLE_JOB_STATES = {'completed', 'canceled', 'failed'}
TASK_FAIL_JOB_PERCENTAGE = 10  # integer from 0 to 100


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

    def jobs_for_project(self, project_id):
        """Returns the jobs for the given project.

        :returns: {'_items': [job, job, ...], '_meta': {Eve metadata}}
        """
        from .sdk import Job

        api = pillar_api()
        try:
            j = Job.all({
                'where': {'project': project_id},
                'sort': [('_updated', -1), ('_created', -1)],
            }, api=api)
        except pillarsdk.ResourceNotFound:
            return {'_items': [], '_meta': {'total': 0}}
        return j

    def job_status_summary(self, project_id):
        """Returns number of shots per shot status for the given project.

        :rtype: ProjectSummary
        """
        from .sdk import Job

        api = pillar_api()

        # TODO: turn this into an aggregation call to do the counting on
        # MongoDB.
        try:
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
        except pillarsdk.ResourceNotFound:
            return ProjectSummary()

        # FIXME: this breaks when we hit the pagination limit.
        summary = ProjectSummary()
        for job in jobs['_items']:
            summary.count(job['status'])

        return summary

    def update_job_after_task_status_change(self, job_id, task_id, new_task_status):
        """Updates the job status based on the status of this task and other tasks in the job.
        """

        def __job_active_if_queued():
            """Set job to active if it was queued."""

            jobs_coll = current_flamenco.db('jobs')
            job = jobs_coll.find_one(job_id, projection={'status': 1})
            if job['status'] == 'queued':
                self._log.info('Job %s became active because one of its tasks %s changed '
                               'status to %s', job_id, task_id, new_task_status)
                self.api_set_job_status(job_id, 'active')

        if new_task_status == {'queued', 'cancel-requested', 'claimed-by-manager'}:
            # Ignore; for now re-queueing a task doesn't change the job status.
            # Also, canceling a single task has no influence on the job itself.
            # A task being claimed by the manager also doesn't change job status.
            return

        if new_task_status == 'canceled':
            # This could be the last cancel-requested task to go to 'canceled.
            tasks_coll = current_flamenco.db('tasks')
            statuses = tasks_coll.distinct('status', {'job': job_id})
            if 'cancel-requested' not in statuses:
                self._log.info('Last task %s of job %s went from cancel-requested to canceld.',
                               task_id, job_id)
                self.api_set_job_status(job_id, 'canceled')
            return

        if new_task_status == 'failed':
            # Count the number of failed tasks. If it is more than 10, fail the job.
            tasks_coll = current_flamenco.db('tasks')
            total_count = tasks_coll.find({'job': job_id}).count()
            fail_count = tasks_coll.find({'job': job_id, 'status': 'failed'}).count()
            fail_perc = fail_count / float(total_count) * 100
            if fail_perc >= TASK_FAIL_JOB_PERCENTAGE:
                self._log.warning('Failing job %s because %i of its %i tasks (%i%%) failed',
                                  job_id, fail_count, total_count, fail_perc)
                self.api_set_job_status(job_id, 'failed')
            else:
                self._log.warning('Task %s of job %s failed; '
                                  'only %i of its %i tasks failed (%i%%), so ignoring for now',
                                  task_id, job_id, fail_count, total_count, fail_perc)
                __job_active_if_queued()
            return

        if new_task_status in {'active', 'processing'}:
            self._log.info('Job %s became active because one of its tasks %s changed status to %s',
                           job_id, task_id, new_task_status)
            self.api_set_job_status(job_id, 'active')
            return

        if new_task_status == 'completed':
            # Maybe all tasks are completed, which should complete the job.
            tasks_coll = current_flamenco.db('tasks')
            statuses = tasks_coll.distinct('status', {'job': job_id})
            if statuses == ['completed']:
                self._log.info('All tasks (last one was %s) of job %s are completed, '
                               'setting job to completed.',
                               task_id, job_id)
                self.api_set_job_status(job_id, 'completed')
            else:
                __job_active_if_queued()
            return

        self._log.warning('Task %s of job %s obtained status %s, '
                          'which we do not know how to handle.',
                          task_id, job_id, new_task_status)

    def web_set_job_status(self, job_id, new_status):
        """Web-level call to updates the job status."""
        from .sdk import Job

        api = pillar_api()
        job = Job({'_id': job_id})
        job.patch({'op': 'set-job-status',
                   'status': new_status}, api=api)

    def api_set_job_status(self, job_id, new_status):
        """API-level call to updates the job status."""

        self._log.info('Setting job %s status to "%s"', job_id, new_status)

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
            return
        elif new_status == 'active':
            # Nothing to do; this happens when a task gets started, which has nothing to
            # do with other tasks in the job.
            return
        elif new_status in {'cancel-requested', 'failed'}:
            # Request cancel of any task that might run on the manager.
            cancelreq_result = current_flamenco.update_status_q(
                'tasks',
                {'job': job_id, 'status': {'$in': ['active', 'claimed-by-manager']}},
                'cancel-requested')
            # Directly cancel any task that might run in the future, but is not touched by
            # a manager yet.
            current_flamenco.update_status_q(
                'tasks',
                {'job': job_id, 'status': 'queued'},
                'canceled')

            # If the new status is cancel-requested, and no tasks were marked as cancel-requested,
            # we can directly transition the job to 'canceled', without waiting for more task
            # updates.
            if new_status == 'cancel-requested' and cancelreq_result.modified_count == 0:
                self._log.info('handle_job_status_change(%s, %s, %s): no cancel-requested tasks, '
                               'so transitioning directly to canceled',
                               job_id, old_status, new_status)
                self.api_set_job_status(job_id, 'canceled')
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
    from . import eve_hooks, patch

    eve_hooks.setup_app(app)
    patch.setup_app(app)
