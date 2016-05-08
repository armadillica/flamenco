import base64
import datetime
import hashlib
import logging
import rsa
import bcrypt
from bson import tz_util
from eve.methods.post import post_internal

from flask import abort, Blueprint, current_app, jsonify, request

from application.utils.authentication import store_token
from application.utils.authentication import create_new_user_document
from application.utils.authentication import make_unique_username

blueprint = Blueprint('authentication', __name__)
log = logging.getLogger(__name__)


def get_auth_credentials(user, provider):
    return next((credentials for credentials in user['auth'] if 'provider'
                 in credentials and credentials['provider'] == provider), None)


def create_local_user(email, password):
    """For internal user only. Given username and password, create a user."""
    # Hash the password
    hashed_password = hash_password(password, bcrypt.gensalt())
    db_user = create_new_user_document(email, '', email, provider='local',
                                       token=hashed_password)
    # Make username unique
    db_user['username'] = make_unique_username(email)
    # Create the user
    r, _, _, status = post_internal('users', db_user)
    if status != 201:
        log.error('internal response: %r %r', status, r)
        return abort(500)
    # Return user ID
    return r['_id']


@blueprint.route('/make-token', methods=['POST'])
def make_token():
    """Direct login for a user, without OAuth, using local database. Generates
    a token that is passed back to Pillar Web and used in subsequent
    transactions.

    :return: a token string
    """
    username = request.form['username']
    password = request.form['password']

    # Look up user in db
    users_collection = current_app.data.driver.db['users']
    user = users_collection.find_one({'username': username})
    if not user:
        return abort(403)
    # Check if user has "local" auth type
    credentials = get_auth_credentials(user, 'local')
    if not credentials:
        return abort(403)
    # Verify password
    salt = credentials['token']
    hashed_password = hash_password(password, salt)
    if hashed_password != credentials['token']:
        return abort(403)
    # Generate Token
    token = base64.b64encode(rsa.randnum.read_random_bits(256))
    # TODO look into alternative implementations
    token_expiry = datetime.datetime.now(tz=tz_util.utc) + datetime.timedelta(
        days=15)
    store_token(user['_id'], token, token_expiry)
    return jsonify(token=token)


def hash_password(password, salt):
    if isinstance(salt, unicode):
        salt = salt.encode('utf-8')
    encoded_password = base64.b64encode(hashlib.sha256(password).digest())
    return bcrypt.hashpw(encoded_password, salt)


def setup_app(app, url_prefix):
    app.register_blueprint(blueprint, url_prefix=url_prefix)
