# -*- encoding: utf-8 -*-

import logging

from flask import Blueprint, render_template, request
import flask_login
import werkzeug.exceptions as wz_exceptions

from pillar.web.system_util import pillar_api
import pillar.api.utils
import pillar.web.subquery

from flamenco.routes import flamenco_project_view
from flamenco import current_flamenco, ROLES_REQUIRED_TO_VIEW_ITEMS

from . import Job

perproject_blueprint = Blueprint('flamenco.jobs.perproject', __name__,
                                 url_prefix='/<project_url>/jobs')
log = logging.getLogger(__name__)


@perproject_blueprint.route('/', endpoint='index')
@flamenco_project_view(extension_props=False)
def for_project(project, job_id=None, task_id=None):
    jobs = current_flamenco.job_manager.jobs_for_project(project['_id'])
    return render_template('flamenco/jobs/list_for_project.html',
                           stats={'nr_of_jobs': u'∞', 'nr_of_tasks': u'∞'},
                           jobs=jobs['_items'],
                           open_job_id=job_id,
                           open_task_id=task_id,
                           project=project)


@perproject_blueprint.route('/with-task/<task_id>')
@flamenco_project_view()
def for_project_with_task(project, task_id):
    from flamenco.tasks import Task

    api = pillar_api()
    task = Task.find(task_id, {'projection': {'job': 1}}, api=api)
    return for_project(project, job_id=task['job'], task_id=task_id)


@perproject_blueprint.route('/<job_id>')
@flamenco_project_view(extension_props=True)
def view_job(project, flamenco_props, job_id):
    if not request.is_xhr:
        return for_project(project, job_id=job_id)

    # Job list is public, job details are not.
    if not flask_login.current_user.has_role(*ROLES_REQUIRED_TO_VIEW_ITEMS):
        raise wz_exceptions.Forbidden()

    api = pillar_api()
    job = Job.find(job_id, api=api)

    return render_template('flamenco/jobs/view_job_embed.html',
                           job=job,
                           project=project,
                           flamenco_props=flamenco_props.to_dict(),
                           flamenco_context=request.args.get('context'))
