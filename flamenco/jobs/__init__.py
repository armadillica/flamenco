"""Job management."""
import typing

import collections
import copy
import datetime

import attr
import bson
from flask import current_app
import pymongo.results
import werkzeug.exceptions as wz_exceptions

import pillarsdk
from pillar import attrs_extra
from pillar.api.utils import random_etag, utcnow
from pillar.web.system_util import pillar_api

from flamenco import current_flamenco

CANCELABLE_JOB_STATES = {'active', 'queued', 'failed'}
REQUEABLE_JOB_STATES = {'completed', 'canceled', 'failed', 'paused'}
RECREATABLE_JOB_STATES = {'canceled', 'completed'}
ARCHIVE_JOB_STATES = {'archiving', 'archived'}  # states that represent more-or-less archived jobs.
ARCHIVEABLE_JOB_STATES = REQUEABLE_JOB_STATES  # states from which a job can be archived.
FAILED_TASKS_REQUEABLE_JOB_STATES = {'active', 'queued'}
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
                       project_id, user_id, manager_id, priority=50,
                       *, start_paused=False):
        """Creates a job, returning a dict with its generated fields."""

        job = {
            'name': job_name,
            'description': job_desc,
            'job_type': job_type,
            'project': project_id,
            'user': user_id,
            'manager': manager_id,
            'status': 'under-construction',
            'priority': int(priority),
            'settings': copy.deepcopy(job_settings),
        }
        if start_paused:
            job['start_paused'] = True

        self._log.info('Creating job %r for user %s and manager %s',
                       job_name, user_id, manager_id)

        r, _, _, status = current_app.post_internal('flamenco_jobs', job)
        if status != 201:
            self._log.error('Status should be 201, not %i: %s' % (status, r))
            raise ValueError('Unable to create Flamenco job, status code %i' % status)

        job.update(r)
        return job

    def jobs_for_project(self, project_id, *, archived=False):
        """Returns the jobs for the given project.

        :returns: {'_items': [job, job, ...], '_meta': {Eve metadata}}
        """
        from .sdk import Job

        # Eve doesn't support '$eq' :(
        status_q = 'archived' if archived else {'$ne': 'archived'}
        where = {'project': project_id,
                 'status': status_q}

        api = pillar_api()
        try:
            j = Job.all({
                'where': where,
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

        jobs_coll = current_flamenco.db('jobs')
        tasks_coll = current_flamenco.db('tasks')

        def __job_status_if_a_then_b(if_status: str, then_new_status: str):
            """Set job to active if it was queued."""

            job = jobs_coll.find_one(job_id, projection={'status': 1})
            if job['status'] == if_status:
                self._log.info('Job %s became %s because one of its tasks %s changed '
                               'status to %s', job_id, then_new_status, task_id, new_task_status)
                self.api_set_job_status(job_id, then_new_status)

        if new_task_status == 'queued':
            # Re-queueing a task on a completed job should re-queue the job too.
            __job_status_if_a_then_b('completed', 'queued')
            return

        if new_task_status == 'claimed-by-manager':
            # See if there are any active tasks left. If the job was active, but a task
            # goes to 'claimed-by-manager', this means the task likely active and now re-queued.
            statuses = tasks_coll.distinct('status', {'job': job_id})
            if 'active' not in statuses:
                __job_status_if_a_then_b('active', 'queued')
            return

        if new_task_status in {'cancel-requested', 'claimed-by-manager'}:
            # A task being claimed by the manager also doesn't change job status.
            # Also, canceling a single task has no influence on the job itself.
            return

        if new_task_status == 'canceled':
            # This could be the last cancel-requested task to go to 'canceled.
            statuses = tasks_coll.distinct('status', {'job': job_id})
            if 'cancel-requested' not in statuses:
                self._log.info('Last task %s of job %s went from cancel-requested to canceled.',
                               task_id, job_id)
                self.api_set_job_status(job_id, 'canceled')
            return

        if new_task_status == 'failed':
            # Count the number of failed tasks. If it is more than 10%, fail the job.
            total_count = tasks_coll.find({'job': job_id}).count()
            fail_count = tasks_coll.find({'job': job_id, 'status': 'failed'}).count()
            fail_perc = fail_count / float(total_count) * 100
            if fail_perc >= TASK_FAIL_JOB_PERCENTAGE:
                self._log.info('Failing job %s because %i of its %i tasks (%i%%) failed',
                               job_id, fail_count, total_count, fail_perc)
                self.api_set_job_status(job_id, 'failed')
            else:
                self._log.info('Task %s of job %s failed; '
                               'only %i of its %i tasks failed (%i%%), so ignoring for now',
                               task_id, job_id, fail_count, total_count, fail_perc)
                __job_status_if_a_then_b('queued', 'active')
            return

        if new_task_status in {'active', 'processing'}:
            job = jobs_coll.find_one(job_id, projection={'status': 1})
            if job['status'] != 'active':
                self._log.info('Job %s became active because one of its tasks %s changed '
                               'status to %s', job_id, task_id, new_task_status)
                self.api_set_job_status(job_id, 'active')
            return

        if new_task_status == 'completed':
            # Maybe all tasks are completed, which should complete the job.
            statuses = tasks_coll.distinct('status', {'job': job_id})
            if statuses == ['completed']:
                self._log.info('All tasks (last one was %s) of job %s are completed, '
                               'setting job to completed.',
                               task_id, job_id)
                self.api_set_job_status(job_id, 'completed')
            else:
                __job_status_if_a_then_b('queued', 'active')
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

    def api_set_job_status(self, job_id: bson.ObjectId, new_status: str,
                           *, now: datetime.datetime = None) -> pymongo.results.UpdateResult:
        """API-level call to updates the job status."""
        assert new_status
        self._log.debug('Setting job %s status to "%s"', job_id, new_status)

        jobs_coll = current_flamenco.db('jobs')
        curr_job = jobs_coll.find_one({'_id': job_id}, projection={'status': 1})
        old_status = curr_job['status']

        # Go through all necessary status transitions.
        result = None  # make sure that 'result' always has a value.
        while new_status:
            result = current_flamenco.update_status('jobs', job_id, new_status, now=now)
            next_status = self.handle_job_status_change(job_id, old_status, new_status)
            old_status, new_status = new_status, next_status

        return result

    def handle_job_status_change(self, job_id: bson.ObjectId,
                                 old_status: str, new_status: str) -> typing.Optional[str]:
        """Updates task statuses based on this job status transition.

        :returns: the new job status, if this status transition should be
            followed by another one.
        """
        self._log.info('status transition job_id %s from %r to %r', job_id, old_status, new_status)

        if new_status in {'completed', 'canceled'}:
            # Nothing to do; this will happen as a response to all tasks receiving this status.
            return
        elif new_status == 'active':
            # Nothing to do; this happens when a task gets started, which has nothing to
            # do with other tasks in the job.
            return
        elif new_status in {'cancel-requested', 'failed'}:
            return self._do_cancel_tasks(job_id, old_status, new_status)
        elif new_status == 'requeued':
            return self._do_requeue(job_id, old_status, new_status)
        elif new_status == 'queued':
            return self._do_check_completion(job_id, new_status)

    def _do_cancel_tasks(self, job_id, old_status, new_status) -> typing.Optional[str]:
        """Directly cancel any task that might run in the future.

        Only cancels tasks that haven't been touched by a manager yet;
        otherwise it requests the Manager to cancel the tasks.

        :returns: the next job status, if a status change is required.
        """

        current_flamenco.update_status_q(
            'tasks',
            {'job': job_id, 'status': 'queued'},
            'canceled')
        # Request cancel of any task that might run on the manager.
        cancelreq_result = current_flamenco.update_status_q(
            'tasks',
            {'job': job_id, 'status': {'$in': ['active', 'claimed-by-manager']}},
            'cancel-requested')
        # Update the activity of all the tasks we just cancelled (or requested cancellation),
        # so that users can tell why they were cancelled.
        current_flamenco.task_manager.api_set_activity(
            {'job': job_id,
             'status': {'$in': ['cancel-requested', 'canceled']},
             'activity': {'$exists': False}},
            'Server cancelled this task because the job got status %r.' % new_status
        )
        # If the new status is cancel-requested, and no tasks were marked as cancel-requested,
        # we can directly transition the job to 'canceled', without waiting for more task
        # updates.
        if new_status == 'cancel-requested' and cancelreq_result.modified_count == 0:
            self._log.info('handle_job_status_change(%s, %s, %s): no cancel-requested tasks, '
                           'so transitioning directly to canceled',
                           job_id, old_status, new_status)
            return 'canceled'

    def _do_requeue(self, job_id, old_status, new_status) -> typing.Optional[str]:
        """Re-queue all tasks of the job, and the job itself.

        :returns: the new job status, if this status transition should be
            followed by another one.
        """
        if old_status == 'under-construction':
            # Nothing to do, the job compiler has just finished its work; the tasks have
            # already been set to 'queued' status.
            self._log.debug('Ignoring job status change %r -> %r', old_status, new_status)
            return

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

        # Update the tasks.
        query['job'] = job_id
        current_flamenco.update_status_q('tasks', query, 'queued')
        return 'queued'

    def _do_check_completion(self, job_id, new_status) -> typing.Optional[str]:
        """Completes the job if all tasks are completed.

        :returns: the new job status, if this status transition should be
            followed by another one.
        """

        tasks_coll = current_flamenco.db('tasks')
        total_tasks = tasks_coll.find({'job': job_id}).count()
        completed_tasks = tasks_coll.find({'job': job_id, 'status': 'completed'}).count()
        if completed_tasks < total_tasks:
            # Not yet completed, so just stay at current status.
            self._log.debug('Job %s has %d of %d tasks completed, staying at status %r',
                            job_id, completed_tasks, total_tasks, new_status)
            return

        self._log.info("Job %s has all %d tasks completed, transition from %r to 'completed'",
                       job_id, total_tasks, new_status)
        return 'completed'

    def archive_job(self, job: dict):
        """Initiates job archival by creating a Celery task for it."""

        from flamenco.celery import job_archival

        job_id = job['_id']
        job_status = job['status']

        if job_status in ARCHIVE_JOB_STATES:
            msg = f'Job {job_id} cannot be archived, it has status {job_status}'
            self._log.info(msg)
            raise wz_exceptions.UnprocessableEntity(msg)

        # Store current job status in a special key so that it can be restored before
        # writing to the archive ZIP file as JSON.
        jobs_coll = current_flamenco.db('jobs')
        jobs_coll.update_one({'_id': job_id},
                             {'$set': {'pre_archive_status': job_status}})

        # Immediately set job status to 'archiving', as this should be reflected ASAP in the
        # database + web interface, rather than waiting for a Celery Worker to pick it up.
        self.api_set_job_status(job_id, 'archiving')

        self._log.info('Creating Celery background task for archival of job %s', job_id)
        job_archival.archive_job.delay(str(job_id))

    def api_set_job_priority(self, job_id: bson.ObjectId, new_priority: int):
        """API-level call to updates the job priority."""
        assert isinstance(new_priority, int)
        self._log.debug('Setting job %s priority to %r', job_id, new_priority)

        jobs_coll = current_flamenco.db('jobs')
        curr_job = jobs_coll.find_one({'_id': job_id}, projection={'priority': 1})
        old_priority = curr_job['priority']

        if old_priority == new_priority:
            self._log.debug('Job %s is already at priority %r', job_id, old_priority)
            return

        new_etag = random_etag()
        now = utcnow()
        jobs_coll = current_flamenco.db('jobs')
        result = jobs_coll.update_one({'_id': job_id},
                                      {'$set': {'priority': new_priority,
                                                '_updated': now,
                                                '_etag': new_etag,
                                                }})
        if result.matched_count != 1:
            self._log.warning('Matched %d jobs while setting job %s to priority %r',
                              result.matched_count, job_id, new_priority)

        tasks_coll = current_flamenco.db('tasks')
        result = tasks_coll.update_many({'job': job_id},
                                        {'$set': {'job_priority': new_priority,
                                                  '_updated': now,
                                                  '_etag': new_etag,
                                                  }})
        self._log.debug('Matched %d tasks while setting job %s to priority %r',
                        result.matched_count, job_id, new_priority)


def setup_app(app):
    from . import eve_hooks, patch

    eve_hooks.setup_app(app)
    patch.setup_app(app)
