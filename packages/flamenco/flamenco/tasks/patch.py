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

    from flamenco import eve_settings
    import datetime
    import uuid
    from bson import tz_util

    # TODO: also inspect other tasks of the same job, and possibly update the job status as well.

    # Doesn't use Eve patch_internal to avoid Eve's authorisation. It doesn't know PATCH is allowed
    # by Flamenco managers.

    valid_statuses = eve_settings.tasks_schema['status']['allowed']
    new_status = patch['status']
    if new_status not in valid_statuses:
        raise wz_exceptions.UnprocessableEntity('Invalid status %s' % new_status)

    # Generate random ETag since we can't compute it from the entire document.
    # This means that a subsequent PUT will change the etag even when the document doesn't
    # change; this is unavoidable without fetching the entire document.
    etag = uuid.uuid4().hex

    tasks_coll = current_flamenco.db('tasks')
    result = tasks_coll.update_one(
        {'_id': task_id},
        {'$set': {'status': new_status,
                  '_updated': datetime.datetime.now(tz=tz_util.utc),
                  '_etag': etag}}
    )

    if result.matched_count < 1:
        raise wz_exceptions.NotFound('Task %s does not exist' % task_id)

    if result.matched_count > 1:
        log.warning('Eek, %i tasks with same ID %s, should be impossible',
                    result.matched_count, task_id)

    log.debug('Updated status of %i task(s) %s', result.modified_count, task_id)
    return '', 204


def setup_app(app):
    app.register_api_blueprint(blueprint, url_prefix='/flamenco/tasks')
