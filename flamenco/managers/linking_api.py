"""API interface for Manager linking."""

import binascii
import datetime
import logging

from flask import Blueprint, request, jsonify
import pymongo.results
import werkzeug.exceptions as wz_exceptions

from bson import tz_util

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


def setup_app(app):
    app.register_api_blueprint(api_blueprint, url_prefix='/flamenco/managers/link')
