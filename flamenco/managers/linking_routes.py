import hashlib
import hmac
import logging
import urllib.parse

from flask import Blueprint, request, render_template, redirect
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils import authorization, str2id
from pillar.auth import current_user

from flamenco import current_flamenco
import flamenco.auth

log = logging.getLogger(__name__)
blueprint = Blueprint('flamenco.managers.linking', __name__, url_prefix='/managers/link')


def check_hmac(secret_key: bytes, message: bytes, received_hash: str):
    """Checks the HMAC of the message, raising a BadRequest exception if it's wrong.

    :param secret_key: the key to use for hashing
    :param message: the message to check
    :param received_hash: hexdigest of the hash to check
    """

    computed_hash = _compute_hash(secret_key, message)
    if not hmac.compare_digest(computed_hash, received_hash):
        log.warning('User %s tries to link a manager but has a bad HMAC', current_user.user_id)
        raise wz_exceptions.BadRequest('bad HMAC')


def _compute_hash(secret_key: bytes, message: bytes) -> str:
    """Returns the hexdigest of the HMAC for this key/message combo."""
    hmac_ob = hmac.new(secret_key, msg=message, digestmod=hashlib.sha256)
    computed_hash = hmac_ob.hexdigest()
    return computed_hash


@blueprint.route('/choose', methods=['GET', 'POST'])
@authorization.require_login(require_cap='flamenco-use')
def index():
    user_id = current_user.user_id

    # Fetch available Managers.
    man_man = current_flamenco.manager_manager
    managers = list(man_man.owned_managers(
        current_user.group_ids, {'_id': 1, 'name': 1}))
    manager_limit_reached = len(managers) >= flamenco.auth.MAX_MANAGERS_PER_USER

    # Get the query arguments
    identifier: str = request.args.get('identifier', '')
    return_url: str = request.args.get('return', '')
    request_hmac: str = request.args.get('hmac', '')

    ident_oid = str2id(identifier)
    keys_coll = current_flamenco.db('manager_linking_keys')

    # Verify the received identifier and return URL.
    key_info = keys_coll.find_one({'_id': ident_oid})
    if key_info is None:
        log.warning('User %s tries to link a manager with an identifier that cannot be found',
                    user_id)
        return render_template('flamenco/managers/linking/key_not_found.html')

    check_hmac(key_info['secret_key'],
               f'{identifier}-{return_url}'.encode('ascii'),
               request_hmac)

    # Only deal with POST data after HMAC verification is performed.
    if request.method == 'POST':
        manager_id = request.form['manager-id']

        if manager_id == 'new':
            manager_name = request.form.get('manager-name', '')
            if not manager_name:
                raise wz_exceptions.UnprocessableEntity('no Manager name given')

            if manager_limit_reached:
                log.warning('User %s tries to create a manager %r, but their limit is reached.',
                            user_id, manager_name)
                raise wz_exceptions.UnprocessableEntity('Manager count limit reached')

            log.info('Creating new Manager named %r for user %s', manager_name, user_id)
            account, mngr_doc, token_data = man_man.create_new_manager(manager_name, '', user_id)
            manager_oid = mngr_doc['_id']
        else:
            log.info('Linking existing Manager %r for user %s', manager_id, user_id)
            manager_oid = str2id(manager_id)

        # Store that this identifier belongs to this ManagerID
        update_res = keys_coll.update_one({'_id': ident_oid},
                                          {'$set': {'manager_id': manager_oid}})
        if update_res.matched_count != 1:
            log.error('Match count was %s when trying to update secret key '
                      'for Manager %s on behalf of user %s',
                      update_res.matched_count, manager_oid, user_id)
            raise wz_exceptions.InternalServerError('Unable to store manager ID')

        log.info('Manager ID %s is stored as belonging to key with identifier %s',
                 manager_oid, identifier)

        # Now redirect the user back to Flamenco Manager in a verifyable way.
        msg = f'{identifier}-{manager_oid}'.encode('ascii')
        mac = _compute_hash(key_info['secret_key'], msg)
        qs = urllib.parse.urlencode({
            'hmac': mac,
            'oid': str(manager_oid),
        })

        direct_to = urllib.parse.urljoin(return_url, f'?{qs}')
        log.info('Directing user to URL %s', direct_to)

        return redirect(direct_to, 307)

    return render_template('flamenco/managers/linking/choose_manager.html',
                           managers=managers,
                           can_create_manager=not manager_limit_reached)
