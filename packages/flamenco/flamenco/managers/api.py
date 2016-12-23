import logging

from flask import Blueprint, request
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils import authorization, authentication

api_blueprint = Blueprint('flamenco.managers', __name__)
log = logging.getLogger(__name__)


def manager_api_call(wrapped):
    """Decorator, performs some standard stuff for Manager API endpoints."""
    import functools

    @authorization.require_login(require_roles={u'service', u'flamenco_manager'}, require_all=True)
    @functools.wraps(wrapped)
    def wrapper(manager_id, *args, **kwargs):
        from flamenco import current_flamenco
        from pillar.api.utils import str2id, mongo

        manager_id = str2id(manager_id)
        manager = mongo.find_one_or_404('flamenco_managers', manager_id)
        if not current_flamenco.manager_manager.user_manages(mngr_doc=manager):
            user_id = authentication.current_user_id()
            log.warning('Service account %s sent startup notification for manager %s of another '
                        'service account', user_id, manager_id)
            raise wz_exceptions.Unauthorized()

        return wrapped(manager_id, request.json, *args, **kwargs)

    return wrapper


@api_blueprint.route('/<manager_id>/startup', methods=['POST'])
@manager_api_call
def startup(manager_id, notification):
    from flamenco import current_flamenco

    log.info('Received startup notification from manager %s %s', manager_id, notification)

    mngr_coll = current_flamenco.db('managers')
    update_res = mngr_coll.update_one(
        {'_id': manager_id},
        {'$set': {
            'url': notification['manager_url'],
            'variables': notification['variables'],
            'stats.nr_of_workers': notification['nr_of_workers'],
        }}
    )
    if update_res.matched_count != 1:
        log.warning('Updating manager %s matched %i documents.',
                    manager_id, update_res.matched_count)
        raise wz_exceptions.InternalServerError('Unable to update manager in database.')

    return '', 204


@api_blueprint.route('/<manager_id>/task-update-batch', methods=['POST'])
@manager_api_call
def task_update_batch(manager_id, task_updates):
    import dateutil.parser
    from pillar.api.utils import jsonify, str2id

    from flamenco import current_flamenco, eve_settings

    if not isinstance(task_updates, list):
        raise wz_exceptions.BadRequest('Expected list of task updates.')

    log.info('Received %i task updates from manager %s', len(task_updates), manager_id)

    tasks_coll = current_flamenco.db('tasks')
    logs_coll = current_flamenco.db('task_logs')

    valid_statuses = set(eve_settings.tasks_schema['status']['allowed'])
    handled_update_ids = []
    total_modif_count = 0

    for task_update in task_updates:
        # Check that this task actually belongs to this manager, before we accept any updates.
        update_id = str2id(task_update['_id'])
        task_id = str2id(task_update['task_id'])
        tmaninfo = tasks_coll.find_one({'_id': task_id}, projection={'manager': 1})

        # For now, we just ignore updates to non-existing tasks. Someone might have just deleted
        # one, for example. This is not a reason to reject the entire batch.
        if tmaninfo is None:
            log.warning('Manager %s sent update for non-existing task %s; ignoring',
                        manager_id, task_id)
            continue

        if tmaninfo['manager'] != manager_id:
            log.warning('Manager %s sent update for task %s which belongs to other manager %s',
                        manager_id, task_id, tmaninfo['manager'])
            continue

        # Store the log for this task, allowing for duplicate log reports.
        task_log = task_update.get('log')
        if task_log:
            received_on_manager = dateutil.parser.parse(task_update['received_on_manager'])
            log_doc = {
                '_id': update_id,
                'task': task_id,
                'received_on_manager': received_on_manager,
                'log': task_log
            }
            logs_coll.replace_one({'_id': update_id}, log_doc, upsert=True)

        # Modify the task, and append the log to the logs collection.
        updates = {
            'task_progress_percentage': task_update.get('task_progress_percentage', 0),
            'current_command_index': task_update.get('current_command_index', 0),
            'command_progress_percentage': task_update.get('command_progress_percentage', 0),
        }
        new_status = task_update.get('task_status')
        if new_status:
            updates['status'] = new_status
            if new_status not in valid_statuses:
                # We have to accept the invalid status, because we're too late in the update
                # pipeline to do anything about it. The alternative is to drop the update or
                # reject the entire batch of updates, which is more damaging to the workflow.
                log.warning('Manager %s sent update for task %s with invalid status %r '
                            '(storing anyway)', manager_id, task_id, new_status)
        new_activity = task_update.get('activity')
        if new_activity:
            updates['activity'] = new_activity
        worker = task_update.get('worker')
        if worker:
            updates['worker'] = worker

        result = tasks_coll.update_one({'_id': task_id}, {'$set': updates})
        total_modif_count += result.modified_count

        handled_update_ids.append(update_id)

    return jsonify({'modified_count': total_modif_count,
                    'handled_update_ids': handled_update_ids})


def setup_app(app):
    app.register_api_blueprint(api_blueprint, url_prefix='/flamenco/managers')
