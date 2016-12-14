import logging
import flask

from pillar.api.utils import authorization

log = logging.getLogger(__name__)
blueprint = flask.Blueprint('flamenco.scheduler', __name__, url_prefix='/scheduler')

# The scheduler is in charge of
# - generating a task (or task list) for each manager request
# - update the task list according to external changes


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
    from pillar.api.utils import jsonify, remove_private_keys, str2id

    manager_id = str2id(manager_id)
    chunk_size = int(flask.request.args.get('chunk_size', 1))
    job_type = flask.request.args.get('job_type')

    log.info('Handing over max %i tasks to manager %s', chunk_size, manager_id)

    # TODO: properly order tasks based on parents' status etc.
    tasks_coll = current_flamenco.db('tasks')
    query = {'status': 'queued'}
    if job_type:
        query['job_type'] = job_type

    tasks = []
    for task in tasks_coll.find(query):
        task['status'] = 'claimed-by-manager'
        r, _, _, status = flask.current_app.put_internal(
            'flamenco_tasks',
            remove_private_keys(task),
            _id=task['_id'])

        if status != 200:
            # When there is an error updating the task, it's simply not returned, and doesn't
            # count towards the chunk size.
            log.warning('Error %i updating Flamenco task %s: %s',
                        status, task['_id'], r)
            continue

        r.pop('_status', None)  # this is the status of the PUT we just did, not of the task itself.

        task.update(r)
        tasks.append(task)

        if len(tasks) >= chunk_size:
            break

    resp = jsonify(tasks)
    return resp
