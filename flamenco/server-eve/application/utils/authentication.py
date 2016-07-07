"""Generic authentication.

Contains functionality to validate tokens, create users and tokens, and make
unique usernames from emails. Calls out to the application.modules.blender_id
module for Blender ID communication.
"""

import logging
import datetime

from bson import tz_util
from flask import g
from flask import request
from flask import current_app
from eve.methods.post import post_internal

log = logging.getLogger(__name__)


def validate_token():
    """Validate the token provided in the request and populate the current_user
    flask.g object, so that permissions and access to a resource can be defined
    from it.

    When the token is successfully validated, sets `g.current_user` to contain
    the user information, otherwise it is set to None.

    @returns True iff the user is logged in with a valid Blender ID token.
    """

    # Default to no user at all.
    g.current_user = None

    _delete_expired_tokens()

    if not request.authorization:
        # If no authorization headers are provided, we are getting a request
        # from a non logged in user. Proceed accordingly.
        log.debug('No authentication headers, so not logged in.')
        return False

    # Check the users to see if there is one with this Blender ID token.
    token = request.authorization.username
    oauth_subclient = request.authorization.password

    db_token = find_token(token, oauth_subclient)
    if not db_token:
        log.debug('Token %s not found in our local database.', token)

        # If no valid token is found in our local database, we issue a new
        # request to the Blender ID server to verify the validity of the token
        # passed via the HTTP header. We will get basic user info if the user
        # is authorized, and we will store the token in our local database.
        from application.modules import blender_id

        db_user, status = blender_id.validate_create_user('', token, oauth_subclient)
    else:
        # log.debug("User is already in our database and token hasn't expired yet.")
        users = current_app.data.driver.db['users']
        db_user = users.find_one(db_token['user'])

    if db_user is None:
        log.debug('Validation failed, user not logged in')
        return False

    g.current_user = {'user_id': db_user['_id'],
                      'groups': db_user['groups'],
                      'roles': set(db_user.get('roles', []))}

    return True


def find_token(token, is_subclient_token=False, **extra_filters):
    """Returns the token document, or None if it doesn't exist (or is expired)."""

    tokens_collection = current_app.data.driver.db['tokens']

    # TODO: remove expired tokens from collection.
    lookup = {'token': token,
              'is_subclient_token': True if is_subclient_token else {'$in': [False, None]},
              'expire_time': {"$gt": datetime.datetime.now(tz=tz_util.utc)}}
    lookup.update(extra_filters)

    db_token = tokens_collection.find_one(lookup)
    return db_token


def store_token(user_id, token, token_expiry, oauth_subclient_id=False):
    """Stores an authentication token.

    :returns: the token document from MongoDB
    """

    token_data = {
        'user': user_id,
        'token': token,
        'expire_time': token_expiry,
    }
    if oauth_subclient_id:
        token_data['is_subclient_token'] = True

    r, _, _, status = post_internal('tokens', token_data)

    if status not in {200, 201}:
        log.error('Unable to store authentication token: %s', r)
        raise RuntimeError('Unable to store authentication token.')

    token_data.update(r)
    return token_data


def create_new_user(email, username, user_id):
    """Creates a new user in our local database.

    @param email: the user's email
    @param username: the username, which is also used as full name.
    @param user_id: the user ID from the Blender ID server.
    @returns: the user ID from our local database.
    """

    user_data = create_new_user_document(email, user_id, username)
    r = post_internal('users', user_data)
    user_id = r[0]['_id']
    return user_id


def create_new_user_document(email, user_id, username, provider='blender-id',
                             token=''):
    """Creates a new user document, without storing it in MongoDB. The token
    parameter is a password in case provider is "local".
    """

    user_data = {
        'full_name': username,
        'username': username,
        'email': email,
        'auth': [{
            'provider': provider,
            'user_id': str(user_id),
            'token': token}],
        'settings': {
            'email_communications': 1
        },
        'groups': [],
    }
    return user_data


def make_unique_username(email):
    """Creates a unique username from the email address.

    @param email: the email address
    @returns: the new username
    @rtype: str
    """

    username = email.split('@')[0]
    # Check for min length of username (otherwise validation fails)
    username = "___{0}".format(username) if len(username) < 3 else username

    users = current_app.data.driver.db['users']
    user_from_username = users.find_one({'username': username})

    if not user_from_username:
        return username

    # Username exists, make it unique by adding some number after it.
    suffix = 1
    while True:
        unique_name = '%s%i' % (username, suffix)
        user_from_username = users.find_one({'username': unique_name})
        if user_from_username is None:
            return unique_name
        suffix += 1


def _delete_expired_tokens():
    """Deletes tokens that have expired.

    For debugging, we keep expired tokens around for a few days, so that we
    can determine that a token was expired rather than not created in the
    first place. It also grants some leeway in clock synchronisation.
    """

    token_coll = current_app.data.driver.db['tokens']

    now = datetime.datetime.now(tz_util.utc)
    expiry_date = now - datetime.timedelta(days=7)

    result = token_coll.delete_many({'expire_time': {"$lt": expiry_date}})
    # log.debug('Deleted %i expired authentication tokens', result.deleted_count)


def current_user_id():
    """None-safe fetching of user ID. Can return None itself, though."""

    current_user = g.get('current_user') or {}
    return current_user.get('user_id')
