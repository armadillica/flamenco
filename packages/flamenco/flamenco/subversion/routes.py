import logging

from flask import Blueprint, render_template, url_for, request, current_app
import werkzeug.exceptions as wz_exceptions

from pillar.api.utils import jsonify
from pillar.api.utils import authorization, authentication

from flamenco import EXTENSION_NAME
from flamenco.routes import flamenco_project_view

blueprint = Blueprint('flamenco.subversion', __name__, url_prefix='/')
api_blueprint = Blueprint('flamenco.api.subversion', __name__, url_prefix='/api')

log = logging.getLogger(__name__)


@blueprint.route('/<project_url>/subversion/kick')
@flamenco_project_view(extension_props=True)
def subversion_kick(project, flamenco_props):
    from flamenco import subversion

    svn_server_url = flamenco_props.svn_url  # 'svn://localhost/agent327'
    log.info('Re-examining SVN server %s', svn_server_url)
    client = subversion.obtain(svn_server_url)

    # TODO: last_seen_revision should be stored, probably at the project level.
    last_seen_revision = 0
    observer = subversion.CommitLogObserver(client, last_seen_revision=last_seen_revision)
    observer.fetch_and_observe()

    return jsonify({
        'previous_last_seen_revision': last_seen_revision,
        'last_seen_revision': observer.last_seen_revision,
    })


@api_blueprint.route('/<project_url>/subversion/log', methods=['POST'])
@authorization.require_login(require_roles={u'service', u'svner'}, require_all=True)
def subversion_log(project_url):
    if request.mimetype != 'application/json':
        log.warning('Received %s instead of application/json', request.mimetype)
        raise wz_exceptions.BadRequest()

    # Parse the request
    args = request.json
    try:
        revision = args['revision']
        commit_message = args['msg']
        commit_author = args['author']
        commit_date = args['date']
    except KeyError as ex:
        log.info('subversion_log(%s): request is missing key %s', project_url, ex)
        raise wz_exceptions.BadRequest()

    current_user_id = authentication.current_user_id()
    log.info('Service account %s registers SVN commit %s of user %s',
             current_user_id, revision, commit_author)
    assert current_user_id

    users_coll = current_app.db()['users']
    projects_coll = current_app.db()['projects']
    project = projects_coll.find_one({'url': project_url},
                                     projection={'_id': 1, 'url': 1,
                                                 'extension_props': 1})
    if not project:
        return 'Project not found', 403

    # Check that the service user is allowed to log on this project.
    srv_user = users_coll.find_one(current_user_id,
                                   projection={'service.svner': 1})
    if srv_user is None:
        log.error('subversion_log(%s): current user %s not found -- how did they log in?',
                  project['url'], current_user_id)
        return 'User not found', 403

    allowed_project = srv_user.get('service', {}).get('svner', {}).get('project')
    if allowed_project != project['_id']:
        log.warning('subversion_log(%s): current user %s not authorized to project %s',
                    project['url'], current_user_id, project['_id'])
        return 'Project not allowed', 403

    from flamenco import subversion

    try:
        flamenco_props = project['extension_props'][EXTENSION_NAME]
    except KeyError:
        return 'Not set up for Flamenco', 400

    svn_server_url = flamenco_props['svn_url']
    log.debug('Receiving commit from SVN server %s', svn_server_url)
    log_entry = subversion.create_log_entry(revision=revision,
                                            msg=commit_message,
                                            author=commit_author,
                                            date_text=commit_date)
    observer = subversion.CommitLogObserver()
    log.debug('Processing %s via %s', log_entry, observer)
    observer.process_log(log_entry)

    return 'Registered in Flamenco'
