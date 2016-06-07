import logging
from flask import Blueprint, current_app, abort, request
from eve.methods.put import put_internal
from eve.methods.get import get
from application.utils.authorization import require_login
from application.utils import jsonify, remove_private_keys


log = logging.getLogger(__name__)
blueprint = Blueprint('scheduler', __name__)

# The scheduler is in charge of
# - generating a task (or task list) for each manager request
# - update the task list according to external changes


@blueprint.route('/tasks')
@require_login()
def generate_tasks():
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
    """
    job_type = request.args.get('job_type', None)
    tasks = current_app.data.driver.db['tasks']
    payload = {'status': 'queued'}
    if job_type:
        payload['job_type'] = job_type

    task = tasks.find_one(payload)
    if task is None:
        return abort(404)
    task_id = task['_id']

    task['status'] = 'processing'
    r, _, _, status = put_internal('tasks', remove_private_keys(task),
                                   _id=task_id)
    task.update(r)
    resp = jsonify(task, status=status)
    return resp


def setup_app(app, url_prefix):
    app.register_blueprint(blueprint, url_prefix=url_prefix)
