import copy
import hashlib
import json
import logging
import urllib

from flask import g, current_app, Blueprint

from werkzeug.exceptions import Forbidden
from eve.utils import parse_request
from eve.methods.get import get

from application.utils.authorization import user_has_role, require_login
from application.utils import jsonify

log = logging.getLogger(__name__)
blueprint = Blueprint('users', __name__)


@blueprint.route('/me')
@require_login()
def my_info():
    eve_resp, _, _, status, _ = get('users', {'_id': g.current_user['user_id']})
    resp = jsonify(eve_resp['_items'][0], status=status)
    return resp


def gravatar(email, size=64):
    parameters = {'s': str(size), 'd': 'mm'}
    return "https://www.gravatar.com/avatar/" + \
           hashlib.md5(str(email)).hexdigest() + \
           "?" + urllib.urlencode(parameters)


def post_GET_user(request, payload):
    json_data = json.loads(payload.data)
    # Check if we are querying the users endpoint (instead of the single user)
    if json_data.get('_id') is None:
        return
    # json_data['computed_permissions'] = \
    #     compute_permissions(json_data['_id'], app.data.driver)
    payload.data = json.dumps(json_data)


def before_replacing_user(request, lookup):
    """Loads the auth field from the database, preventing any changes."""

    # Find the user that is being replaced
    req = parse_request('users')
    req.projection = json.dumps({'auth': 1})
    original = current_app.data.find_one('users', req, **lookup)

    # Make sure that the replacement has a valid auth field.
    updates = request.get_json()
    assert updates is request.get_json()  # We should get a ref to the cached JSON, and not a copy.

    if 'auth' in original:
        updates['auth'] = copy.deepcopy(original['auth'])
    else:
        updates.pop('auth', None)


def push_updated_user_to_algolia(user, original):
    """Push an update to the Algolia index when a user item is updated"""

    from algoliasearch.client import AlgoliaException
    from application.utils.algolia import algolia_index_user_save

    try:
        algolia_index_user_save(user)
    except AlgoliaException as ex:
        log.warning('Unable to push user info to Algolia for user "%s", id=%s; %s',
                    user.get('username'), user.get('_id'), ex)


def send_blinker_signal_roles_changed(user, original):
    """Sends a Blinker signal that the user roles were changed, so others can respond."""

    if user.get('roles') == original.get('roles'):
        return

    from application.modules.service import signal_user_changed_role

    log.info('User %s changed roles to %s, sending Blinker signal',
             user.get('_id'), user.get('roles'))
    signal_user_changed_role.send(current_app, user=user)


def check_user_access(request, lookup):
    """Modifies the lookup dict to limit returned user info."""

    # No access when not logged in.
    current_user = g.get('current_user')
    current_user_id = current_user['user_id'] if current_user else None

    # Admins can do anything and get everything, except the 'auth' block.
    if user_has_role(u'admin'):
        return

    if not lookup and not current_user:
        raise Forbidden()

    # Add a filter to only return the current user.
    if '_id' not in lookup:
        lookup['_id'] = current_user['user_id']


def check_put_access(request, lookup):
    """Only allow PUT to the current user, or all users if admin."""

    if user_has_role(u'admin'):
        return

    current_user = g.get('current_user')
    if not current_user:
        raise Forbidden()

    if str(lookup['_id']) != str(current_user['user_id']):
        raise Forbidden()


def after_fetching_user(user):
    # Deny access to auth block; authentication stuff is managed by
    # custom end-points.
    user.pop('auth', None)

    current_user = g.get('current_user')
    current_user_id = current_user['user_id'] if current_user else None

    # Admins can do anything and get everything, except the 'auth' block.
    if user_has_role(u'admin'):
        return

    # Only allow full access to the current user.
    if str(user['_id']) == str(current_user_id):
        return

    # Remove all fields except public ones.
    public_fields = {'full_name', 'email'}
    for field in list(user.keys()):
        if field not in public_fields:
            del user[field]


def after_fetching_user_resource(response):
    for user in response['_items']:
        after_fetching_user(user)


def setup_app(app, url_prefix):
    app.on_pre_GET_users += check_user_access
    app.on_post_GET_users += post_GET_user
    app.on_pre_PUT_users += check_put_access
    app.on_pre_PUT_users += before_replacing_user
    app.on_replaced_users += push_updated_user_to_algolia
    app.on_replaced_users += send_blinker_signal_roles_changed
    app.on_fetched_item_users += after_fetching_user
    app.on_fetched_resource_users += after_fetching_user_resource

    app.register_blueprint(blueprint, url_prefix=url_prefix)
