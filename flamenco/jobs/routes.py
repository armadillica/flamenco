# -*- encoding: utf-8 -*-

import collections
import functools
import logging

import bson
from flask import Blueprint, render_template, request, redirect, url_for
import werkzeug.exceptions as wz_exceptions

import pillarsdk
import pillar.flask_extra
from pillar.web.system_util import pillar_api
from pillar.auth import current_user
from pillar import current_app

from flamenco.routes import flamenco_project_view
from flamenco import current_flamenco
from flamenco.auth import Actions

blueprint = Blueprint('flamenco.jobs', __name__, url_prefix='/jobs')
perproject_blueprint = Blueprint('flamenco.jobs.perproject', __name__,
                                 url_prefix='/<project_url>/jobs')
perproject_archive_blueprint = Blueprint('flamenco.jobs.archive.perproject', __name__,
                                         url_prefix='/<project_url>/archive')
blueprint_for_archived = {
    False: perproject_blueprint,
    True: perproject_archive_blueprint,
}

log = logging.getLogger(__name__)

# The job statuses that can be set from the web-interface.
ALLOWED_JOB_STATUSES_FROM_WEB = {'cancel-requested', 'queued', 'requeued'}


@perproject_blueprint.route('/', endpoint='index')
@perproject_archive_blueprint.route('/', endpoint='index')
@flamenco_project_view(extension_props=False, action=Actions.VIEW)
def for_project(project, job_id=None, task_id=None):
    api = pillar_api()

    is_archive = request.blueprint == perproject_archive_blueprint.name
    jobs = current_flamenco.job_manager.jobs_for_project(project['_id'],
                                                         archived=is_archive)

    # See if we need to redirect between archive and non-archive view.
    if job_id and not any(job['_id'] == job_id for job in jobs['_items']):
        target_blueprint = blueprint_for_archived[not is_archive]
        target_endpoint = request.endpoint.split('.')[-1]
        new_url = url_for(f'{target_blueprint.name}.{target_endpoint}', **request.view_args)
        return redirect(new_url, code=307)

    @functools.lru_cache()
    def manager_name(manager_id: str) -> str:
        from ..managers.sdk import Manager

        try:
            manager = Manager.find(manager_id, api=api)
        except pillarsdk.ForbiddenAccess:
            # It's possible that the user doesn't have access to this Manager.
            return '-unknown-'
        except pillarsdk.ResourceNotFound:
            log.warning('Unable to find manager %r for job list of project %s',
                        manager_id, project['_id'])
            return '-unknown-'
        return manager['name'] or '-unknown-'

    # Find the link URL and Manager name for each job.
    for job in jobs['_items']:
        target_blueprint = blueprint_for_archived[job.status == 'archived']
        job.url = url_for(f'{target_blueprint.name}.view_job',
                          project_url=project.url, job_id=job._id)
        job.manager_name = manager_name(job['manager'])

    return render_template('flamenco/jobs/list_for_project.html',
                           stats={'nr_of_jobs': '∞', 'nr_of_tasks': '∞'},
                           jobs=jobs['_items'],
                           open_job_id=job_id,
                           open_task_id=task_id,
                           project=project,
                           is_archive=is_archive,
                           page_context='archive' if is_archive else 'job')


@perproject_blueprint.route('/with-task/<task_id>')
@perproject_archive_blueprint.route('/with-task/<task_id>')
@flamenco_project_view(action=Actions.VIEW)
def for_project_with_task(project, task_id):
    from flamenco.tasks.sdk import Task

    api = pillar_api()
    task = Task.find(task_id, {'projection': {'job': 1}}, api=api)
    return for_project(project, job_id=task['job'], task_id=task_id)


@perproject_blueprint.route('/<job_id>')
@perproject_archive_blueprint.route('/<job_id>')
@pillar.flask_extra.vary_xhr()
@flamenco_project_view(extension_props=True, action=Actions.VIEW)
def view_job(project, flamenco_props, job_id):
    if not request.is_xhr:
        return for_project(project, job_id=job_id)

    # Job list is public, job details are not.
    if not current_user.has_cap('flamenco-view'):
        raise wz_exceptions.Forbidden()

    from .sdk import Job
    from ..managers.sdk import Manager

    api = pillar_api()
    job = Job.find(job_id, api=api)

    try:
        manager = Manager.find(job.manager, api=api)
    except pillarsdk.ForbiddenAccess:
        # It's very possible that the user doesn't have access to this Manager.
        manager = None
    except pillarsdk.ResourceNotFound:
        log.warning('Flamenco job %s has a non-existant manager %s', job_id, job.manager)
        manager = None

    users_coll = current_app.db('users')
    user = users_coll.find_one(bson.ObjectId(job.user), projection={'username': 1})
    if user:
        user_name = user.get('username') or '-unknown-'
    else:
        user_name = '-unknown-'

    from . import (CANCELABLE_JOB_STATES, REQUEABLE_JOB_STATES, RECREATABLE_JOB_STATES,
                   ARCHIVE_JOB_STATES, ARCHIVEABLE_JOB_STATES, FAILED_TASKS_REQUEABLE_JOB_STATES)

    auth = current_flamenco.auth
    write_access = auth.current_user_may(auth.Actions.USE, bson.ObjectId(project['_id']))

    status = job['status']
    is_archived = status in ARCHIVE_JOB_STATES
    archive_available = is_archived and job.archive_blob_name

    # Sort job settings so we can iterate over them in a deterministic way.
    job_settings = collections.OrderedDict((key, job.settings[key])
                                           for key in sorted(job.settings.to_dict().keys()))

    change_prio_states = RECREATABLE_JOB_STATES | REQUEABLE_JOB_STATES | CANCELABLE_JOB_STATES

    return render_template(
        'flamenco/jobs/view_job_embed.html',
        job=job,
        user_name=user_name,
        manager=manager,
        project=project,
        flamenco_props=flamenco_props.to_dict(),
        flamenco_context=request.args.get('context'),
        can_cancel_job=write_access and status in CANCELABLE_JOB_STATES,
        can_requeue_job=write_access and status in REQUEABLE_JOB_STATES,
        can_recreate_job=write_access and status in RECREATABLE_JOB_STATES,
        can_archive_job=write_access and status in ARCHIVEABLE_JOB_STATES,
        # TODO(Sybren): check that there are actually failed tasks before setting to True:
        can_requeue_failed_tasks=write_access and status in FAILED_TASKS_REQUEABLE_JOB_STATES,
        can_change_prio=write_access and status in change_prio_states,
        is_archived=is_archived,
        write_access=write_access,
        archive_available=archive_available,
        job_settings=job_settings,
    )


@perproject_blueprint.route('/<job_id>/archive')
@flamenco_project_view(extension_props=False, action=Actions.USE)
def archive(project, job_id):
    """Redirects to the actual job archive.

    This is done via a redirect, so that templates that offer a download link do not
    need to know the eventual storage backend link. This makes them render faster,
    and only requires communication with the storage backend when needed.
    """

    from pillar.api.file_storage_backends import default_storage_backend

    from . import ARCHIVE_JOB_STATES
    from .sdk import Job

    api = pillar_api()
    job = Job.find(job_id, api=api)

    if job['status'] not in ARCHIVE_JOB_STATES:
        raise wz_exceptions.PreconditionFailed('Job is not archived')

    archive_blob_name = job.archive_blob_name
    if not archive_blob_name:
        raise wz_exceptions.NotFound('Job has no archive')

    bucket = default_storage_backend(project._id)
    blob = bucket.get_blob(archive_blob_name)
    archive_url = blob.get_url(is_public=False)

    return redirect(archive_url, code=303)


@perproject_blueprint.route('/<job_id>/depsgraph')
@flamenco_project_view(extension_props=False, action=Actions.VIEW)
def view_job_depsgraph(project, job_id):
    # Job list is public, job details are not.
    if not current_user.has_cap('flamenco-view'):
        raise wz_exceptions.Forbidden()

    focus_task_id = request.args.get('t', None)
    return render_template('flamenco/jobs/depsgraph.html',
                           job_id=job_id,
                           project=project,
                           focus_task_id=focus_task_id)


@perproject_blueprint.route('/<job_id>/depsgraph-data')
@perproject_blueprint.route('/<job_id>/depsgraph-data/<focus_task_id>')
@flamenco_project_view(extension_props=False, action=Actions.VIEW)
def view_job_depsgraph_data(project, job_id, focus_task_id=None):
    # Job list is public, job details are not.
    if not current_user.has_cap('flamenco-view'):
        raise wz_exceptions.Forbidden()

    import collections
    from flask import jsonify
    from flamenco.tasks import COLOR_FOR_TASK_STATUS
    from pillar.web.utils import last_page_index

    # Collect tasks page-by-page. Stored in a dict to prevent duplicates.
    tasks = {}

    LIMITED_RESULT_COUNT = 8

    def query_tasks(extra_where, extra_update, limit_results: bool):
        page_idx = 1
        added_in_this_query = 0
        while True:
            task_page = current_flamenco.task_manager.tasks_for_job(
                job_id,
                page=page_idx,
                max_results=LIMITED_RESULT_COUNT if limit_results else 250,
                extra_where=extra_where)
            for task in task_page._items:
                if task._id in tasks:
                    continue
                task = task.to_dict()
                task.update(extra_update)
                tasks[task['_id']] = task
                added_in_this_query += 1

            if limit_results and added_in_this_query >= LIMITED_RESULT_COUNT:
                break

            if page_idx >= last_page_index(task_page._meta):
                break
            page_idx += 1

    if focus_task_id is None:
        # Get the top-level tasks as 'focus tasks'.
        # TODO: Test for case of multiple top-level tasks.
        extra_where = {
            'parents': {'$exists': 0},
        }
    else:
        # Otherwise just put in the focus task ID; querying like this ensures
        # the returned task belongs to the current job.
        extra_where = {'_id': focus_task_id}

    log.debug('Querying tasks, focused on %s', extra_where)
    query_tasks(extra_where, {'_generation': 0}, False)

    # Query for the children & parents of these tasks
    already_queried_parents = set()
    already_queried_children = set()

    def add_parents_children(generation: int, is_outside: bool):
        nonlocal already_queried_parents
        nonlocal already_queried_children

        if not tasks:
            return

        if is_outside:
            extra_update = {'_outside': True}
        else:
            extra_update = {}

        parent_ids = {parent
                      for task in tasks.values()
                      for parent in task.get('parents', ())}

        # Get the children of these tasks, but only those we haven't queried for already.
        query_children = set(tasks.keys()) - already_queried_children
        if query_children:
            update = {'_generation': generation, **extra_update}
            query_tasks({'parents': {'$in': list(query_children)}}, update, is_outside)
            already_queried_children.update(query_children)

        # Get the parents of these tasks, but only those we haven't queried for already.
        query_parents = parent_ids - already_queried_parents
        if query_parents:
            update = {'_generation': -generation, **extra_update}
            query_tasks({'_id': {'$in': list(query_parents)}}, update, False)
            already_queried_parents.update(query_parents)

    # Add parents/children and grandparents/grandchildren.
    # This queries too much, but that's ok for now; this is just a debugging tool.
    log.debug('Querying first-level family')
    add_parents_children(1, False)
    log.debug('Querying second-level family')
    add_parents_children(2, True)

    # nodes and edges are only told apart by (not) having 'source' and 'target' properties.
    graph_items = []
    roots = []
    xpos_per_generation = collections.defaultdict(int)
    for task in sorted(tasks.values(), key=lambda task: task['priority']):
        gen = task['_generation']
        xpos = xpos_per_generation[gen]
        xpos_per_generation[gen] += 1

        graph_items.append({
            'group': 'nodes',
            'data': {
                'id': task['_id'],
                'label': task['name'],
                'status': task['status'],
                'color': COLOR_FOR_TASK_STATUS[task['status']],
                'outside': task.get('_outside', False),
                'focus': task['_id'] == focus_task_id,
            },
            'position': {'x': xpos * 100, 'y': gen * -100},
        })
        if task.get('parents'):
            for parent in task['parents']:
                # Skip edges to tasks that aren't even in the graph.
                if parent not in tasks: continue

                graph_items.append({
                    'group': 'edges',
                    'data': {
                        'id': '%s-%s' % (task['_id'], parent),
                        'target': task['_id'],
                        'source': parent,
                    }
                })
        else:
            roots.append(task['_id'])
    return jsonify(elements=graph_items, roots=roots)


@perproject_blueprint.route('/<job_id>/recreate', methods=['POST'])
@flamenco_project_view(extension_props=False)
def recreate_job(project: pillarsdk.Project, job_id):
    from pillar.api.utils.authentication import current_user_id
    from pillar.api.utils import str2id

    log.info('Recreating job %s on behalf of user %s', job_id, current_user_id())

    job_id = str2id(job_id)
    current_flamenco.api_recreate_job(job_id)

    return '', 204


@blueprint.route('/<job_id>/set-status', methods=['POST'])
def set_job_status(job_id):
    from flask_login import current_user

    # FIXME Sybren: add permission check.

    new_status = request.form['status']
    if new_status not in ALLOWED_JOB_STATUSES_FROM_WEB:
        log.warning('User %s tried to set status of job %s to disallowed status "%s"; denied.',
                    current_user.objectid, job_id, new_status)
        raise wz_exceptions.UnprocessableEntity('Status "%s" not allowed' % new_status)

    log.info('User %s set status of job %s to "%s"', current_user.objectid, job_id, new_status)
    current_flamenco.job_manager.web_set_job_status(job_id, new_status)

    return '', 204


@blueprint.route('/<job_id>/redir')
def redir_job_id(job_id):
    """Redirects to the job view.

    This saves the client from performing another request to find the project URL;
    we do it for them.
    """

    from flask import redirect, url_for
    from .sdk import Job
    from pillarsdk import Project

    # FIXME Sybren: add permission check.

    api = pillar_api()
    j = Job.find(job_id, {'projection': {'project': 1, 'status': 1}}, api=api)
    p = Project.find(j.project, {'projection': {'url': 1}}, api=api)

    target_blueprint = blueprint_for_archived[j.status == 'archived']
    return redirect(url_for(f'{target_blueprint.name}.view_job',
                            project_url=p.url, job_id=j._id))
