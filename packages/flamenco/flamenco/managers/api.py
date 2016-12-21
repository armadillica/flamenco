import logging

from flask import Blueprint, request
import flask_login
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils import authorization, authentication

api_blueprint = Blueprint('flamenco.managers', __name__)
log = logging.getLogger(__name__)


@api_blueprint.route('/<manager_id>/startup', methods=['POST'])
@authorization.require_login(require_roles={u'service', u'flamenco_manager'}, require_all=True)
def startup(manager_id):
    from flamenco import current_flamenco
    from pillar.api.utils import str2id, mongo

    manager_id = str2id(manager_id)
    manager = mongo.find_one_or_404('flamenco_managers', manager_id)
    if not current_flamenco.manager_manager.user_manages(mngr_doc=manager):
        user_id = authentication.current_user_id()
        log.warning('Service account %s sent startup notification for manager %s of another '
                    'service account', user_id, manager_id)
        raise wz_exceptions.Unauthorized()

    notification = request.json

    log.info('Received startup notification from manager %s', manager_id)
    log.info('Contents:\n%s\n', notification)

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


def setup_app(app):
    app.register_api_blueprint(api_blueprint, url_prefix='/flamenco/managers')
