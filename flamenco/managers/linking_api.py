"""API interface for Manager linking."""

import binascii
import datetime
import logging

import attr
from bson import tz_util
from flask import Blueprint, request, jsonify
import pymongo.results
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils import str2id

api_blueprint = Blueprint('flamenco.managers.linking_api', __name__)
log = logging.getLogger(__name__)

EXPIRE_AFTER = datetime.timedelta(minutes=15)


@api_blueprint.route('/exchange', methods=['POST'])
def exchange():
    """Receives a secret key from a Manager that wants to link.

    Stores the secret key, and returns the ObjectID of that document.
    """

    from flamenco import current_flamenco
    import datetime

    # See if we got a key at all.
    data = request.get_json()
    secret_key_hex = data.get('key')
    if not secret_key_hex:
        raise wz_exceptions.BadRequest('No key given')

    # Transform the key from hex to binary data.
    try:
        secret_key = binascii.a2b_hex(secret_key_hex)
    except binascii.Error:
        raise wz_exceptions.BadRequest('Malformed key')

    # Store the key in the database.
    log.info('Received secret key from manager at %s', request.remote_addr)
    mngr_key_coll = current_flamenco.db('manager_linking_keys')
    insert_res: pymongo.results.InsertOneResult = mngr_key_coll.insert_one({
        'secret_key': secret_key,
        'remove_after': datetime.datetime.now(tz=tz_util.utc) + EXPIRE_AFTER,
    })

    identifier = insert_res.inserted_id
    if not identifier:
        log.error('No inserted_id after inserting secret key!')
        raise wz_exceptions.InternalServerError('Unable to store key')

    return jsonify({'identifier': str(identifier)})


@api_blueprint.route('/reset-token', methods=['POST'])
def reset_token():
    """Generates a new authentication token for the Manager.

    The Manager must have exchanged a secret key first, which must be linked to a Manager ID
    before this function can be called.
    """

    from flamenco import current_flamenco
    from .linking_routes import check_hmac

    data = request.get_json()
    identifier = str2id(data.get('identifier'))
    manager_id = str2id(data.get('manager_id'))
    padding = data.get('padding', '')
    mac = data.get('hmac')

    log.info('Received request to reset auth token for Manager %s', manager_id)
    mngr_key_coll = current_flamenco.db('manager_linking_keys')
    key_info = mngr_key_coll.find_one({'_id': identifier, 'manager_id': manager_id})
    if not key_info or not key_info.get('secret_key'):
        log.warning('No secret key found for identifier %s, manager %s', identifier, manager_id)
        raise wz_exceptions.BadRequest('No secret key exchanged')

    check_hmac(key_info['secret_key'],
               f'{padding}-{identifier}-{manager_id}'.encode('ascii'),
               mac)

    auth_token_info = current_flamenco.manager_manager.gen_new_auth_token(manager_id)
    if not auth_token_info:
        raise wz_exceptions.NotFound()

    del_res = mngr_key_coll.delete_many({'manager_id': manager_id})
    log.info('Authentication token reset for Manager %s, all %d secret key(s) for this'
             ' manager have been removed.', manager_id, del_res.deleted_count)

    return jsonify(attr.asdict(auth_token_info))


def setup_app(app):
    app.register_api_blueprint(api_blueprint, url_prefix='/flamenco/managers/link')
