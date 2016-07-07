"""Blender ID subclient endpoint.

Also contains functionality for other parts of Pillar to perform communication
with Blender ID.
"""

import logging
import datetime

from bson import tz_util
import requests
from requests.adapters import HTTPAdapter
from flask import Blueprint, request, current_app, abort, jsonify
from eve.methods.post import post_internal
from eve.methods.put import put_internal
from werkzeug import exceptions as wz_exceptions

from application.utils import authentication, remove_private_keys

blender_id = Blueprint('blender_id', __name__)
log = logging.getLogger(__name__)


@blender_id.route('/store_scst', methods=['POST'])
def store_subclient_token():
    """Verifies & stores a user's subclient-specific token."""

    user_id = request.form['user_id']  # User ID at BlenderID
    subclient_id = request.form['subclient_id']
    scst = request.form['token']

    db_user, status = validate_create_user(user_id, scst, subclient_id)

    if db_user is None:
        log.warning('Unable to verify subclient token with Blender ID.')
        return jsonify({'status': 'fail',
                        'error': 'BLENDER ID ERROR'}), 403

    return jsonify({'status': 'success',
                    'subclient_user_id': str(db_user['_id'])}), status


def blender_id_endpoint():
    """Gets the endpoint for the authentication API. If the env variable
    is defined, it's possible to override the (default) production address.
    """
    return current_app.config['BLENDER_ID_ENDPOINT'].rstrip('/')


def validate_create_user(blender_id_user_id, token, oauth_subclient_id):
    """Validates a user against Blender ID, creating the user in our database.

    :param blender_id_user_id: the user ID at the BlenderID server.
    :param token: the OAuth access token.
    :param oauth_subclient_id: the subclient ID, or empty string if not a subclient.
    :returns: (user in MongoDB, HTTP status 200 or 201)
    """

    # Verify with Blender ID
    log.debug('Storing token for BlenderID user %s', blender_id_user_id)
    user_info, token_expiry = validate_token(blender_id_user_id, token, oauth_subclient_id)

    if user_info is None:
        log.debug('Unable to verify token with Blender ID.')
        return None, None

    # Blender ID can be queried without user ID, and will always include the
    # correct user ID in its response.
    log.debug('Obtained user info from Blender ID: %s', user_info)
    blender_id_user_id = user_info['id']

    # Store the user info in MongoDB.
    db_user = find_user_in_db(blender_id_user_id, user_info)
    db_id, status = upsert_user(db_user, blender_id_user_id)

    # Store the token in MongoDB.
    authentication.store_token(db_id, token, token_expiry, oauth_subclient_id)

    return db_user, status


def upsert_user(db_user, blender_id_user_id):
    """Inserts/updates the user in MongoDB.

    Retries a few times when there are uniqueness issues in the username.

    :returns: the user's database ID and the status of the PUT/POST.
        The status is 201 on insert, and 200 on update.
    :type: (ObjectId, int)
    """

    r = {}
    for retry in range(5):
        if '_id' in db_user:
            # Update the existing user
            attempted_eve_method = 'PUT'
            db_id = db_user['_id']
            r, _, _, status = put_internal('users', remove_private_keys(db_user),
                                           _id=db_id)
            if status == 422:
                log.error('Status %i trying to PUT user %s with values %s, should not happen! %s',
                          status, db_id, remove_private_keys(db_user), r)
        else:
            # Create a new user, retry for non-unique usernames.
            attempted_eve_method = 'POST'
            r, _, _, status = post_internal('users', db_user)

            if status not in {200, 201}:
                log.error('Status %i trying to create user for BlenderID %s with values %s: %s',
                          status, blender_id_user_id, db_user, r)
                raise wz_exceptions.InternalServerError()

            db_id = r['_id']
            db_user.update(r)  # update with database/eve-generated fields.

        if status == 422:
            # Probably non-unique username, so retry a few times with different usernames.
            log.info('Error creating new user: %s', r)
            username_issue = r.get('_issues', {}).get(u'username', '')
            if u'not unique' in username_issue:
                # Retry
                db_user['username'] = authentication.make_unique_username(db_user['email'])
                continue

        # Saving was successful, or at least didn't break on a non-unique username.
        break
    else:
        log.error('Unable to create new user %s: %s', db_user, r)
        raise wz_exceptions.InternalServerError()

    if status not in (200, 201):
        log.error('internal response from %s to Eve: %r %r', attempted_eve_method, status, r)
        raise wz_exceptions.InternalServerError()

    return db_id, status


def validate_token(user_id, token, oauth_subclient_id):
    """Verifies a subclient token with Blender ID.

    :returns: (user info, token expiry) on success, or (None, None) on failure.
        The user information from Blender ID is returned as dict
        {'email': 'a@b', 'full_name': 'AB'}, token expiry as a datime.datetime.
    :rtype: dict
    """

    our_subclient_id = current_app.config['BLENDER_ID_SUBCLIENT_ID']

    # Check that IF there is a subclient ID given, it is the correct one.
    if oauth_subclient_id and our_subclient_id != oauth_subclient_id:
        log.warning('validate_token(): BlenderID user %s is trying to use the wrong subclient '
                    'ID %r; treating as invalid login.', user_id, oauth_subclient_id)
        return None, None

    # Validate against BlenderID.
    log.debug('Validating subclient token for BlenderID user %r, subclient %r', user_id,
              oauth_subclient_id)
    payload = {'user_id': user_id,
               'token': token}
    if oauth_subclient_id:
        payload['subclient_id'] = oauth_subclient_id

    url = '{0}/u/validate_token'.format(blender_id_endpoint())
    log.debug('POSTing to %r', url)

    # Retry a few times when POSTing to BlenderID fails.
    # Source: http://stackoverflow.com/a/15431343/875379
    s = requests.Session()
    s.mount(blender_id_endpoint(), HTTPAdapter(max_retries=5))

    # POST to Blender ID, handling errors as negative verification results.
    try:
        r = s.post(url, data=payload, timeout=5)
    except requests.exceptions.ConnectionError as e:
        log.error('Connection error trying to POST to %s, handling as invalid token.', url)
        return None, None

    if r.status_code != 200:
        log.debug('Token %s invalid, HTTP status %i returned', token, r.status_code)
        return None, None

    resp = r.json()
    if resp['status'] != 'success':
        log.warning('Failed response from %s: %s', url, resp)
        return None, None

    expires = _compute_token_expiry(resp['token_expires'])

    return resp['user'], expires


def _compute_token_expiry(token_expires_string):
    """Computes token expiry based on current time and BlenderID expiry.

    Expires our side of the token when either the BlenderID token expires,
    or in one hour. The latter case is to ensure we periodically verify
    the token.
    """

    date_format = current_app.config['RFC1123_DATE_FORMAT']
    blid_expiry = datetime.datetime.strptime(token_expires_string, date_format)
    blid_expiry = blid_expiry.replace(tzinfo=tz_util.utc)
    our_expiry = datetime.datetime.now(tz=tz_util.utc) + datetime.timedelta(hours=1)

    return min(blid_expiry, our_expiry)


def find_user_in_db(blender_id_user_id, user_info):
    """Find the user in our database, creating/updating the returned document where needed.

    Does NOT update the user in the database.
    """

    users = current_app.data.driver.db['users']

    query = {'auth': {'$elemMatch': {'user_id': str(blender_id_user_id),
                                     'provider': 'blender-id'}}}
    log.debug('Querying: %s', query)
    db_user = users.find_one(query)

    if db_user:
        log.debug('User blender_id_user_id=%r already in our database, '
                  'updating with info from Blender ID.', blender_id_user_id)
        db_user['email'] = user_info['email']
    else:
        log.debug('User %r not yet in our database, create a new one.', blender_id_user_id)
        db_user = authentication.create_new_user_document(
            email=user_info['email'],
            user_id=blender_id_user_id,
            username=user_info['full_name'])
        db_user['username'] = authentication.make_unique_username(user_info['email'])
        if not db_user['full_name']:
            db_user['full_name'] = db_user['username']

    return db_user
