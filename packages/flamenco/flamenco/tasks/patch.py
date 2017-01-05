"""Task patching support."""

import logging

import werkzeug.exceptions as wz_exceptions
from flask import Blueprint, request
from pillar.api.utils import authorization, authentication, str2id

from flamenco import current_flamenco

log = logging.getLogger(__name__)
blueprint = Blueprint('flamenco.tasks.patch', __name__)

patch_handlers = {}


def patch_handler(operation):
    """Decorator, marks the decorated function as PATCH handler."""

    def decorator(func):
        patch_handlers[operation] = func
        return func

    return decorator


@blueprint.route('/<task_id>', methods=['PATCH'])
@authorization.require_login()
def patch_task(task_id):
    # Parse the request
    task_id = str2id(task_id)
    patch = request.get_json()

    try:
        patch_op = patch['op']
    except KeyError:
        raise wz_exceptions.BadRequest("PATCH should contain 'op' key to denote operation.")

    log.debug('User %s wants to PATCH %s task %s',
              authentication.current_user_id(), patch_op, task_id)

    # Find the PATCH handler for the operation.
    try:
        handler = patch_handlers[patch_op]
    except KeyError:
        log.warning('No PATCH handler for operation %r', patch_op)
        raise wz_exceptions.BadRequest('Operation %r not supported' % patch_op)

    # Let the PATCH handler do its thing.
    return handler(task_id, patch)


@patch_handler(u'set-task-status')
@authorization.require_login(require_roles={u'service', u'flamenco_manager'}, require_all=True)
def patch_set_task_status(task_id, patch):
    """Updates a task's status in the database."""

    from flamenco import current_flamenco
    from pillar.api.utils import str2id

    new_status = patch['status']
    task_id = str2id(task_id)

    try:
        current_flamenco.update_status('tasks', task_id, new_status)
    except ValueError:
        raise wz_exceptions.UnprocessableEntity('Invalid status')

    tasks_coll = current_flamenco.db('tasks')


    return '', 204


def setup_app(app):
    app.register_api_blueprint(blueprint, url_prefix='/flamenco/tasks')
