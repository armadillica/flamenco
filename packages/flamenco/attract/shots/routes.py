import logging

import flask_login
from flask import Blueprint, render_template, request
import flask
import werkzeug.exceptions as wz_exceptions

import pillarsdk
import pillar.api.utils
from pillar.web.system_util import pillar_api

from attract.routes import attract_project_view
from attract.node_types.shot import node_type_shot
from attract import current_attract, ROLES_REQUIRED_TO_VIEW_ITEMS
from pillar.web.utils import get_file

perproject_blueprint = Blueprint('attract.shots.perproject', __name__,
                                 url_prefix='/<project_url>/shots')
log = logging.getLogger(__name__)


@perproject_blueprint.route('/', endpoint='index')
@perproject_blueprint.route('/with-task/<task_id>', endpoint='with_task')
@attract_project_view(extension_props=True)
def for_project(project, attract_props, task_id=None, shot_id=None):
    api = pillar_api()

    found = pillarsdk.Node.all({
        'where': {
            'project': project['_id'],
            'node_type': node_type_shot['name'],
        },
        'sort': [
            ('properties.cut_in_timeline_in_frames', 1),
        ]
    }, api=api)
    shots = found['_items']

    thumb_placeholder = flask.url_for('static_attract', filename='assets/img/placeholder.jpg')
    for shot in shots:
        picture = get_file(shot.picture, api=api)
        if picture:
            shot._thumbnail = next((var.link for var in picture.variations
                                    if var.size == 't'), thumb_placeholder)
        else:
            shot._thumbnail = thumb_placeholder

        # The placeholder can be shown quite small, but otherwise the aspect ratio of
        # the actual thumbnail should be taken into account. Since it's different for
        # each project, we can't hard-code a proper height.
        shot._thumbnail_height = '30px' if shot._thumbnail is thumb_placeholder else 'auto'

    tasks_for_shots = current_attract.shot_manager.tasks_for_shots(
        shots,
        attract_props.task_types.attract_shot,
    )

    # Append the task type onto which 'other' tasks are mapped.
    task_types = attract_props.task_types.attract_shot + [None]

    # Some aggregated stats
    stats = {
        'nr_of_shots': sum(shot.properties.used_in_edit for shot in shots),
        'total_frame_count': sum(shot.properties.duration_in_edit_in_frames or 0
                                 for shot in shots
                                 if shot.properties.used_in_edit),
    }

    return render_template('attract/shots/for_project.html',
                           shots=shots,
                           tasks_for_shots=tasks_for_shots,
                           task_types=task_types,
                           open_task_id=task_id,
                           open_shot_id=shot_id,
                           project=project,
                           attract_props=attract_props,
                           stats=stats)


@perproject_blueprint.route('/<shot_id>')
@attract_project_view(extension_props=True)
def view_shot(project, attract_props, shot_id):
    if not request.is_xhr:
        return for_project(project, attract_props, shot_id=shot_id)

    # Shot list is public, shot details are not.
    if not flask_login.current_user.has_role(*ROLES_REQUIRED_TO_VIEW_ITEMS):
        raise wz_exceptions.Forbidden()

    api = pillar_api()

    shot = pillarsdk.Node.find(shot_id, api=api)
    node_type = project.get_node_type(node_type_shot['name'])

    return render_template('attract/shots/view_shot_embed.html',
                           shot=shot,
                           project=project,
                           shot_node_type=node_type,
                           attract_props=attract_props)


@perproject_blueprint.route('/<shot_id>', methods=['POST'])
@attract_project_view()
def save(project, shot_id):
    log.info('Saving shot %s', shot_id)
    log.debug('Form data: %s', request.form)

    shot_dict = request.form.to_dict()
    current_attract.shot_manager.edit_shot(shot_id, **shot_dict)

    # Return the patched node in all its glory.
    api = pillar_api()
    shot = pillarsdk.Node.find(shot_id, api=api)
    return pillar.api.utils.jsonify(shot.to_dict())


# TODO: remove GET method once Pablo has made a proper button to call this URL with a POST.
@perproject_blueprint.route('/create', methods=['POST', 'GET'])
@attract_project_view()
def create_shot(project):
    shot = current_attract.shot_manager.create_shot(project)

    resp = flask.make_response()
    resp.headers['Location'] = flask.url_for('.view_shot',
                                             project_url=project['url'],
                                             shot_id=shot['_id'])
    resp.status_code = 201
    return flask.make_response(flask.jsonify({'shot_id': shot['_id']}), 201)


@perproject_blueprint.route('/<shot_id>/activities')
@attract_project_view()
def activities(project, shot_id):
    if not request.is_xhr:
        return flask.redirect(flask.url_for('.view_shot',
                                            project_url=project.url,
                                            shot_id=shot_id))

    acts = current_attract.activities_for_node(shot_id)
    return flask.render_template('attract/shots/view_activities_embed.html',
                                 activities=acts)
