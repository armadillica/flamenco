import datetime
import logging

from pillar import current_app
from pillar.api.utils import utcnow

from flamenco import current_flamenco

log = logging.getLogger(__name__)


@current_app.celery.task(ignore_result=True)
def remove_waiting_for_files():
    """Deletes jobs that are stuck in 'waiting-for-files' status.

    These jobs are waiting for an external PATCH call to initiate job
    compilation, queueing, and execution. If this PATCH call doesn't
    come, the job is stuck in this status. After a certain time of
    waiting, this function will automatically delete those jobs.

    Be sure to add a schedule to the Celery Beat like this:

    'remove_waiting_for_files': {
        'task': 'flamenco.celery.job_cleanup.remove_waiting_for_files',
        'schedule': 3600,  # every N seconds
    }
    """
    age = current_app.config['FLAMENCO_WAITING_FOR_FILES_MAX_AGE']  # type: datetime.timedelta
    assert isinstance(age, datetime.timedelta), \
        f'FLAMENCO_WAITING_FOR_FILES_MAX_AGE should be a timedelta, not {age!r}'

    threshold = utcnow() - age
    log.info('Deleting jobs stuck in "waiting-for-files" status that have not been '
             'updated since %s', threshold)

    jobs_coll = current_flamenco.db('jobs')
    result = jobs_coll.delete_many({
        'status': 'waiting-for-files',
        '_updated': {'$lt': threshold},
    })

    # No need to delete the tasks, because those jobs don't have any.
    log.info('Deleted %d jobs stuck in "waiting-for-files" status', result.deleted_count)
