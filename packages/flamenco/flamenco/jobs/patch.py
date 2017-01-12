"""Job patching support.

TODO Sybren: merge identical code in jobs/patch.py and tasks/patch.py into
something more generic/reusable.
"""

import logging

import werkzeug.exceptions as wz_exceptions
from flask import Blueprint, request
from pillar.api.utils import authorization, authentication, str2id

log = logging.getLogger(__name__)
patch_api_blueprint = Blueprint('flamenco.jobs.patch', __name__)

patch_handlers = {}


def patch_handler(operation):
    """Decorator, marks the decorated function as PATCH handler."""

    def decorator(func):
        patch_handlers[operation] = func
        return func

    return decorator


@patch_api_blueprint.route('/<job_id>', methods=['PATCH'])
@authorization.require_login()
def patch_job(job_id):
    # Parse the request
    job_id = str2id(job_id)
    patch = request.get_json()

    try:
        patch_op = patch['op']
    except KeyError:
        raise wz_exceptions.BadRequest("PATCH should contain 'op' key to denote operation.")

    log.debug('User %s wants to PATCH "%s" job %s',
              authentication.current_user_id(), patch_op, job_id)

    # Find the PATCH handler for the operation.
    try:
        handler = patch_handlers[patch_op]
    except KeyError:
        log.warning('No PATCH handler for operation %r', patch_op)
        raise wz_exceptions.BadRequest('Operation %r not supported' % patch_op)

    # Let the PATCH handler do its thing.
    return handler(job_id, patch)


@patch_handler(u'set-job-status')
@authorization.require_login(require_roles={u'flamenco-admin'})
def patch_set_job_status(job_id, patch):
    """Updates a job's status in the database."""

    from flamenco import current_flamenco
    from pillar.api.utils import str2id
    from pillar.api.utils.authentication import current_user_id

    new_status = patch['status']
    job_id = str2id(job_id)

    log.info('User %s uses PATCH to set job %s status to "%s"',
             current_user_id(), job_id, new_status)
    try:
        current_flamenco.job_manager.api_set_job_status(job_id, new_status)
    except ValueError:
        raise wz_exceptions.UnprocessableEntity('Status %s is invalid' % new_status)

    return '', 204


def setup_app(app):
    app.register_api_blueprint(patch_api_blueprint, url_prefix='/flamenco/jobs')
