import functools
import logging

import bson
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required
import werkzeug.exceptions as wz_exceptions

from pillar.auth import current_web_user as current_user
from pillar.api.utils.authentication import current_user_id
from pillar.web.utils import attach_project_pictures
from pillar.web.system_util import pillar_api
from pillar.web.projects.routes import project_view
import pillarsdk

from flamenco import current_flamenco
import flamenco.auth

blueprint = Blueprint('flamenco', __name__)
log = logging.getLogger(__name__)


@blueprint.route('/')
def index():
    api = pillar_api()

    # FIXME Sybren: add permission check.
    # TODO: add projections.
    projects = current_flamenco.flamenco_projects()

    for project in projects['_items']:
        attach_project_pictures(project, api)

    projs_with_summaries = [
        (proj, current_flamenco.job_manager.job_status_summary(proj['_id']))
        for proj in projects['_items']
    ]

    return render_template('flamenco/index.html',
                           projs_with_summaries=projs_with_summaries)


def error_project_not_setup_for_flamenco():
    return render_template('flamenco/errors/project_not_setup.html')


def error_project_not_available():
    import flask

    if flask.request.is_xhr:
        resp = flask.jsonify({'_error': 'project not available on Flamenco'})
        resp.status_code = 403
        return resp

    return render_template('flamenco/errors/project_not_available.html')


def flamenco_project_view(extra_project_projections: dict = None,
                          *,
                          extension_props=False,
                          action=flamenco.auth.Actions.USE):
    """Decorator, replaces the first parameter project_url with the actual project.

    Assumes the first parameter to the decorated function is 'project_url'. It then
    looks up that project, checks that it's set up for Flamenco, and passes it to the
    decorated function.

    If not set up for flamenco, uses error_project_not_setup_for_flamenco() to render
    the response.

    :param extra_project_projections: extra projections to use on top of the ones already
        used by this decorator.
    :param extension_props: when True, passes (project, extension_props) as first parameters
        to the decorated function. When False, just passes (project, ).
    :param action: when USE, requires that a Flamenco Manager is assigned
        to the project, and that the user has access to this manager (i.e. is part of this
        project).
    """

    from flask import session
    import flask_login

    from . import EXTENSION_NAME

    if callable(extra_project_projections):
        raise TypeError('Use with @flamenco_project_view() <-- note the parentheses')

    projections = {
        '_id': 1,
        'name': 1,
        'permissions': 1,
        'extension_props.%s' % EXTENSION_NAME: 1,
        # We don't need this here, but this way the wrapped function has access
        # to the orignal URL passed to it.
        'url': 1,
    }
    if extra_project_projections:
        projections.update(extra_project_projections)

    def decorator(wrapped):
        @functools.wraps(wrapped)
        def wrapper(project_url, *args, **kwargs):
            if isinstance(project_url, pillarsdk.Resource):
                # This is already a resource, so this call probably is from one
                # view to another. Assume the caller knows what he's doing and
                # just pass everything along.
                return wrapped(project_url, *args, **kwargs)

            api = pillar_api()

            project = pillarsdk.Project.find_by_url(
                project_url,
                {'projection': projections},
                api=api)

            is_flamenco = current_flamenco.is_flamenco_project(project)
            if not is_flamenco:
                return error_project_not_setup_for_flamenco()

            session['flamenco_last_project'] = project.to_dict()

            project_id = bson.ObjectId(project['_id'])
            auth = current_flamenco.auth
            if not auth.current_user_may(action, project_id):
                log.info('Denying user %s access %s to Flamenco on project %s',
                         flask_login.current_user, action, project_id)
                return error_project_not_available()

            if extension_props:
                pprops = project.extension_props.flamenco
                return wrapped(project, pprops, *args, **kwargs)
            return wrapped(project, *args, **kwargs)

        return wrapper

    return decorator


@blueprint.route('/<project_url>')
@flamenco_project_view(extension_props=False)
def project_index(project):
    return redirect(url_for('flamenco.jobs.perproject.index', project_url=project.url))


@blueprint.route('/<project_url>/help')
@flamenco_project_view(extension_props=False)
def help(project):
    return render_template('flamenco/help.html', statuses=[])


@blueprint.route('/<project_url>/setup-for-flamenco', methods=['POST'])
@login_required
@project_view()
def setup_for_flamenco(project: pillarsdk.Project):
    from pillar.api.utils import str2id
    import flamenco.setup
    from flamenco.managers.sdk import Manager

    project_id = project._id

    if not project.has_method('PUT'):
        log.warning('User %s tries to set up project %s for Flamenco, but has no PUT rights.',
                    current_user, project_id)
        raise wz_exceptions.Forbidden()

    if not current_flamenco.auth.current_user_is_flamenco_user():
        log.warning('User %s tries to set up project %s for Flamenco, but is not flamenco-user.',
                    current_user, project_id)
        raise wz_exceptions.Forbidden()

    log.info('User %s sets up project %s for Flamenco', current_user, project_id)
    flamenco.setup.setup_for_flamenco(project.url)

    # Find the Managers available to this user, so we can auto-assign if there is exactly one.
    man_man = current_flamenco.manager_manager
    managers = man_man.owned_managers([bson.ObjectId(gid) for gid in current_user.groups])
    manager_count = managers.count()

    project_oid = str2id(project_id)
    user_id = current_user_id()

    if manager_count == 0:
        _, mngr_doc, _ = man_man.create_new_manager('My Manager', '', user_id)
        assign_man_oid = mngr_doc['_id']
        log.info('Created and auto-assigning Manager %s to project %s upon setup for Flamenco.',
                 assign_man_oid, project_oid)
        man_man.api_assign_to_project(assign_man_oid, project_oid, 'assign')

    elif manager_count == 1:
        assign_manager = managers.next()
        assign_man_oid = str2id(assign_manager['_id'])
        log.info('Auto-assigning Manager %s to project %s upon setup for Flamenco.',
                 assign_man_oid, project_oid)
        man_man.api_assign_to_project(assign_man_oid, project_oid, 'assign')

    return '', 204


def project_settings(project: pillarsdk.Project, **template_args: dict):
    """Renders the project settings page for Flamenco projects."""

    from pillar.api.utils import str2id
    from pillar.web.system_util import pillar_api
    from .managers.sdk import Manager

    # Based on the project state, we can render a different template.
    if not current_flamenco.is_flamenco_project(project):
        return render_template('flamenco/project_settings/offer_setup.html',
                               project=project, **template_args)

    project_id = str2id(project['_id'])
    flauth = current_flamenco.auth
    may_use = flauth.current_user_may(flauth.Actions.USE, project_id)

    # Use the API for querying for Managers, because it implements access control.
    api = pillar_api()
    managers = Manager.all(api=api)
    linked_managers = Manager.all({
        'where': {
            'projects': project['_id'],
        },
    }, api=api)

    try:
        first_manager = managers['_items'][0]
    except (KeyError, IndexError):
        first_manager = None
    try:
        first_linked_manager = linked_managers['_items'][0]
    except (KeyError, IndexError):
        first_linked_manager = None

    return render_template('flamenco/project_settings/settings.html',
                           project=project,
                           managers=managers,
                           first_manager=first_manager,
                           linked_managers=linked_managers,
                           first_linked_manager=first_linked_manager,
                           may_use_flamenco=may_use,
                           **template_args)
