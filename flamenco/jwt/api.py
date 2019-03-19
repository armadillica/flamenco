import hmac
import logging

import dateutil.parser
from flask import Blueprint, Response, request
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils import authorization, authentication, str2id, mongo, utcnow
from pillar.auth import cors

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
@cors.allow(allow_credentials=True)
@authorization.require_login(require_cap='flamenco-use')
def generate_token(manager_id: str):
    manager_oid = str2id(manager_id)
    manager = mongo.find_one_or_404('flamenco_managers', manager_oid)

    # There are two ways in which a user can get here. One is authenticated via
    # Bearer token, and the other is via an already-existing browser session.
    # In the latter case it's a redirect from a Flamenco Manager and we need to
    # check the timeout and HMAC.
    if not request.headers.get('Authorization', '').startswith('Bearer '):
        hasher = current_flamenco.manager_manager.hasher(manager_oid)
        if hasher is None:
            raise wz_exceptions.InternalServerError('Flamenco Manager not linked to this server')

        expires = request.args.get('expires', '')
        string_to_hash = f'{expires}-{manager_id}'
        hasher.update(string_to_hash.encode('utf8'))
        actual_hmac = hasher.hexdigest()

        query_hmac = request.args.get('hmac', '')
        if not hmac.compare_digest(query_hmac, actual_hmac):
            raise wz_exceptions.Unauthorized('Bad HMAC')

        # Only parse the timestamp after we learned we can trust it.
        expire_timestamp = dateutil.parser.parse(expires)
        validity_seconds_left = (expire_timestamp - utcnow()).total_seconds()
        if validity_seconds_left < 0:
            raise wz_exceptions.Unauthorized('Link expired')
        if validity_seconds_left > 900:
            # Flamenco Manager generates links that are valid for less than a minute, so
            # if it's more than 15 minutes in the future, it's bad.
            raise wz_exceptions.Unauthorized('Link too far in the future')

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
    key_for_manager = jwt.generate_key_for_manager(manager_oid, user.user_id)

    return Response(key_for_manager, content_type='text/plain')


def setup_app(app):
    app.register_api_blueprint(api_blueprint, url_prefix='/flamenco/jwt')
