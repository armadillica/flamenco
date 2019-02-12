"""Runnability checks for active jobs.

A job can be in status 'active' but still unable to run any task. This happens
when all tasks that are still queued are dependent on failed tasks, where the
number of failed tasks is too low to trigger cancellation of the entire job.

Schedule regular checks in the CELERY_BEAT_SCHEDULE like this:

{
    'job-runnability-check': {
        'task': 'flamenco.celery.job_runnability_check.schedule_checks',
        'schedule': 600,  # every N seconds
    },
}


"""

import logging
import typing

from bson import ObjectId

from pillar import current_app

from flamenco import current_flamenco
from flamenco.tasks import FAILED_TASK_STATES, QUEUED_TASK_STATES

log = logging.getLogger(__name__)


@current_app.celery.task(ignore_result=True)
def schedule_checks():
    """Schedules a runnability check for all active jobs."""

    jobs_coll = current_flamenco.db('jobs')
    for job in jobs_coll.find({'status': 'active'}, projection={'_id': True}):
        log.info('Scheduling runnability check of job %s', job['_id'])
        runnability_check.delay(str(job['_id']))


@current_app.celery.task(ignore_result=True)
def runnability_check(job_id: str):
    log.info('checking job %s', job_id)
    job_oid = ObjectId(job_id)

    jobs_coll = current_flamenco.db('jobs')
    job = jobs_coll.find_one({'_id': job_oid})
    if not job:
        log.info('job %s does not exist (any more)', job_id)
        return
    if job['status'] != 'active':
        log.info('job %s is not active any more (status=%r now)', job_id, job['status'])
        return

    unrunnable_task_ids = _nonrunnable_tasks(job_oid)
    if not unrunnable_task_ids:
        log.info('job %s has no non-runnable tasks', job_id)
        return

    log.info('Non-runnable tasks in job %s, failing job: %s',
             job_id, ', '.join([str(tid) for tid in unrunnable_task_ids]))

    reason = f'{len(unrunnable_task_ids)} tasks have a failed/cancelled parent ' \
        f'and will not be able to run.'
    current_flamenco.job_manager.api_set_job_status(
        job_oid, new_status='fail-requested', reason=reason)


def _nonrunnable_tasks(job_oid: ObjectId) -> typing.List[ObjectId]:
    aggr = [
        # Select only tasks that have a runnable status.
        {'$match': {
            'status': {'$in': list(QUEUED_TASK_STATES)},
            'job': job_oid,
        }},
        # Unwind the parents array, so that we can do a lookup in the next stage.
        # Remove any tasks that don't have a parent to begin with.
        {"$unwind": {
            "path": "$parents",
            "preserveNullAndEmptyArrays": False,
        }},
        # Look up the parent document for each unwound task.
        # This produces single-item "parent_doc" arrays.
        {"$lookup": {
            "from": "flamenco_tasks",
            "localField": "parents",
            "foreignField": "_id",
            "as": "parent_doc",
        }},
        # Unwind again, to turn the single-item "parent_doc" arrays into a subdocument.
        {"$unwind": {
            "path": "$parent_doc",
            "preserveNullAndEmptyArrays": False,
        }},
        # Match to find any runnable task with failed/cancelled parent. If this exists,
        # the job will not be able to finish completely, and we'll be better off
        # cancelling it immediately.
        {"$match": {
            'parent_doc.status': {'$in': list(FAILED_TASK_STATES)},
        }},
        {"$project": {"_id": 1}},
    ]
    tasks_coll = current_flamenco.task_manager.collection()
    unrunnable_task_ids = [result['_id']
                           for result in tasks_coll.aggregate(aggr)]
    return unrunnable_task_ids
