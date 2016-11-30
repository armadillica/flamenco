import logging

from flask import Blueprint, render_template, request
import flask
import flask_login
import werkzeug.exceptions as wz_exceptions

import pillarsdk
from pillar.web.system_util import pillar_api
import pillar.api.utils
import pillar.web.subquery

from flamenco.routes import flamenco_project_view
from flamenco import current_flamenco, ROLES_REQUIRED_TO_VIEW_ITEMS

from . import Job

blueprint = Blueprint('flamenco.jobs', __name__, url_prefix='/jobs')
perproject_blueprint = Blueprint('flamenco.jobs.perproject', __name__,
                                 url_prefix='/<project_url>/jobs')
log = logging.getLogger(__name__)


@blueprint.route('/')
def index():
    user = flask_login.current_user
    if not user.is_authenticated:
        return render_template('flamenco/jobs/index.html')

    jobs = current_flamenco.job_manager.jobs_for_user(user.objectid)
    return render_template('flamenco/jobs/for_user.html',
                           jobs=jobs['_items'],
                           job_count=jobs['_meta']['total'])


@blueprint.route('/<job_id>', methods=['DELETE'])
def delete(job_id):
    log.info('Deleting job %s', job_id)

    etag = request.form['etag']
    current_flamenco.job_manager.delete_job(job_id, etag)

    return '', 204


@perproject_blueprint.route('/', endpoint='index')
@flamenco_project_view(extension_props=True)
def for_project(project, flamenco_props, job_id=None):
    jobs = current_flamenco.job_manager.jobs_for_project(project['_id'])
    return render_template('flamenco/jobs/for_project.html',
                           stats={'nr_of_jobs': 0, 'total_frame_count': 0},
                           jobs=jobs['_items'],
                           open_job_id=job_id,
                           project=project)


@perproject_blueprint.route('/<job_id>')
@flamenco_project_view(extension_props=True)
def view_job(project, flamenco_props, job_id):
    if not request.is_xhr:
        return for_project(project, flamenco_props, job_id=job_id)

    # Job list is public, job details are not.
    if not flask_login.current_user.has_role(*ROLES_REQUIRED_TO_VIEW_ITEMS):
        raise wz_exceptions.Forbidden()

    api = pillar_api()
    job = Job.find(job_id, api=api)
    # node_type = project.get_node_type(node_type_job['name'])

    # Fetch project users so that we can assign them jobs
    if 'PUT' in job.allowed_methods:
        users = project.get_users(api=api)
        project.users = users['_items']
    else:
        job.properties.assigned_to.users = [pillar.web.subquery.get_user_info(uid)
                                             for uid in job.properties.assigned_to.users]

    return render_template('flamenco/jobs/view_job_embed.html',
                           job=job,
                           project=project,
                           flamenco_props=flamenco_props.to_dict(),
                           flamenco_context=request.args.get('context'))


@perproject_blueprint.route('/<job_id>', methods=['POST'])
@flamenco_project_view()
def save(project, job_id):
    log.info('Saving job %s', job_id)
    log.debug('Form data: %s', request.form)

    job_dict = request.form.to_dict()
    job_dict['users'] = request.form.getlist('users')

    job = current_flamenco.job_manager.edit_job(job_id, **job_dict)

    return pillar.api.utils.jsonify(job.to_dict())


@perproject_blueprint.route('/create', methods=['POST'])
@flamenco_project_view()
def create_job(project):
    job_type = request.form['job_type']
    parent = request.form.get('parent', None)

    job = current_flamenco.job_manager.create_job(project,
                                                  job_type=job_type,
                                                  parent=parent)

    resp = flask.make_response()
    resp.headers['Location'] = flask.url_for('.view_job',
                                             project_url=project['url'],
                                             job_id=job['_id'])
    resp.status_code = 201

    return flask.make_response(flask.jsonify({'job_id': job['_id']}), 201)
