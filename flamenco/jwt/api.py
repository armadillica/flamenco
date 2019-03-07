import logging

from flask import Blueprint, Response, request
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils import authorization, authentication, str2id, mongo

from flamenco import current_flamenco

api_blueprint = Blueprint('flamenco.jwt.api', __name__)
log = logging.getLogger(__name__)


@api_blueprint.route('/public-keys')
def public_keys():
    if not current_flamenco.jwt.usable:
        raise wz_exceptions.NotImplemented('JWT keystore is not usable at the moment')

    last_modified = current_flamenco.jwt.public_keys_last_modified
    if request.headers.get('If-Modified-Since', '') == last_modified:
        return Response('', status=304)  # Not Modified

    pubs = current_flamenco.jwt.public_keys
    if not pubs:
        raise wz_exceptions.NotImplemented('No public JWT keys available')
    return Response(pubs, content_type='text/plain',
                    headers={'Last-Modified': last_modified})


@api_blueprint.route('/generate-token/<manager_id>')
@authorization.require_login(require_cap='flamenco-use')
def generate_token(manager_id: str):
    manager_oid = str2id(manager_id)
    manager = mongo.find_one_or_404('flamenco_managers', manager_oid)
    user = authentication.current_user()

    if not current_flamenco.manager_manager.user_may_use(mngr_doc=manager):
        log.warning(
            'Account %s called %s for manager %s without access to that manager',
            user.user_id, request.url, manager_oid)
        raise wz_exceptions.Unauthorized()

    jwt = current_flamenco.jwt
    if not jwt.usable:
        raise wz_exceptions.NotImplemented('JWT keystore is not usable at the moment')

    log.info('Generating JWT key for user_id=%s manager_id=%s remote_addr=%s',
             user.user_id, manager_id, request.remote_addr)
    return jwt.generate_key_for_manager(manager_oid, user.user_id)


def setup_app(app):
    app.register_api_blueprint(api_blueprint, url_prefix='/flamenco/jwt')
