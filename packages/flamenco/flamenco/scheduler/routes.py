import logging
import flask

from pillar.api.utils import authorization

log = logging.getLogger(__name__)
blueprint = flask.Blueprint('flamenco.scheduler', __name__, url_prefix='/scheduler')

# The scheduler is in charge of
# - generating a task (or task list) for each manager request
# - update the task list according to external changes

CLAIMED_STATUS = 'claimed-by-manager'


@blueprint.route('/tasks/<manager_id>')
@authorization.require_login(require_roles={u'service', u'flamenco_manager'}, require_all=True)
def schedule_tasks(manager_id):
    """Upon request from a manager, picks the first task available and returns
    it in JSON format.
    Read from request args:
    - job_type (e.g. simple_blender_render)
    - worker (optional, the worker name)
    - Validate request (is it a manager?)
    - Get manager document
    - Query by manager and job_type (sort by priority and creation date)
    - TODO: allow multiple tasks to be requested
    - Optionally handle the 'worker' arg

    This is an API endpoint, so we interface directly with the database.
    """

    from flamenco import current_flamenco
    from pillar.api.utils import jsonify, str2id

    manager_id = str2id(manager_id)
    chunk_size = int(flask.request.args.get('chunk_size', 1))
    job_type = flask.request.args.get('job_type')

    log.debug('Handing over max %i tasks to manager %s', chunk_size, manager_id)

    # TODO: properly order tasks based on parents' status etc.
    tasks_coll = current_flamenco.db('tasks')
    query = {
        'status': 'queued',
        'manager': manager_id,
    }
    if job_type:
        query['job_type'] = job_type

    tasks = []
    affected_jobs = set()
    for task in tasks_coll.find(query):
        # The _updated and _etag fields will be wrong due to the update below, so
        # let's remove them from the response.
        task['status'] = CLAIMED_STATUS
        task.pop('_etag', None)
        task.pop('_updated', None)
        tasks.append(task)
        affected_jobs.add(task['job'])

        if len(tasks) >= chunk_size:
            break

    if not tasks:
        # Nothing to hand out.
        return jsonify([])

    # Do an update directly via MongoDB and not via Eve. Doing it via Eve
    # requires permissions to do a GET on the task, which we don't want
    # to allow to managers (to force them to use the scheduler).
    tasks_coll.update_many(
        {'_id': {'$in': [task['_id'] for task in tasks]}},
        {'$set': {'status': CLAIMED_STATUS}}
    )

    log.info('Handing over %i tasks to manager %s', len(tasks), manager_id)

    # Update the affected jobs.
    for job_id in affected_jobs:
        current_flamenco.job_manager.update_job_after_task_status_change(job_id, 'unknown',
                                                                         CLAIMED_STATUS)

    resp = jsonify(tasks)
    return resp
