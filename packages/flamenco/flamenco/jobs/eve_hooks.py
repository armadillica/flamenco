# -*- encoding: utf-8 -*-

import logging

import itertools
from flask import current_app, g

from pillar.api.nodes import only_for_node_type_decorator
import pillar.api.activities
import pillar.api.utils.authentication
import pillar.web.jinja

from flamenco.node_types.job import node_type_job

log = logging.getLogger(__name__)
only_for_job = only_for_node_type_decorator(node_type_job['name'])


@only_for_job
def fetch_job_extra_info(node):
    """Extends the node with some info about its parent and project.

    This allows us to link to the shot the job is attached to.
    However, such a link requires at least knowing the parent node type,
    which we thus embed here.
    """

    fetch_job_parent_info(node)
    fetch_job_project_info(node)


def fetch_job_parent_info(node):
    """Store node parent info in node['_parent_info']."""

    parent_id = node.get('parent')
    if not parent_id:
        return

    nodes_coll = current_app.db()['nodes']
    parent = nodes_coll.find_one({'_id': parent_id},
                                 projection={'node_type': 1,
                                             'name': 1})
    if parent is None:
        log.warning("Job node %s has parent %s, but the parent doesn't exist.",
                    node['_id'], parent_id)
        return

    parent.pop('_id')  # always there, but also already included in the node.
    node['_parent_info'] = parent


def fetch_job_project_info(node):
    """Store node project info in node['_project_info']."""

    project_id = node.get('project')
    if not project_id:
        log.warning('Job node %s has no project!', node['_id'])
        return

    proj_coll = current_app.db()['projects']
    project = proj_coll.find_one({'_id': project_id},
                                 projection={'name': 1,
                                             'url': 1})
    if project is None:
        log.warning("Job node %s has project %s, but the project doesn't exist.",
                    node['_id'], project_id)
        return

    project.pop('_id')  # always there, but also already included in the node.
    node['_project_info'] = project


def fetch_jobs_parent_info(nodes):
    for node in nodes['_items']:
        fetch_job_extra_info(node)


# ### Activity logging ### #
def _parent_name(job):
    """Returns 'for shot "shotname"' if the job is attached to the shot."""

    parent = job.get('parent')
    if not parent:
        return ''

    nodes_coll = current_app.db()['nodes']
    shot = nodes_coll.find_one(parent)
    if shot:
        return ' for shot "%s"' % shot['name']

    return ''


def register_job_activity(job, descr):
    user_id = pillar.api.utils.authentication.current_user_id()

    context_ob = job.get('parent')
    context_type = 'node'
    if not context_ob:
        context_type = 'project'
        context_ob = job['project']

    pillar.api.activities.register_activity(
        user_id,
        descr + _parent_name(job),
        'node', job['_id'],
        context_type, context_ob,
        job['project'],
        node_type=job['node_type'],
    )


def get_user_list(user_list):
    if not user_list:
        return u'-nobody-'

    user_coll = current_app.db()['users']
    users = user_coll.find(
        {'_id': {'$in': user_list}},
        projection={
            'full_name': 1,
        }
    )

    names = [user['full_name'] for user in users]
    return u', '.join(names)


@only_for_job
def activity_after_replacing_job(job, original):
    # Compare to original, and either mention the things that changed,
    # or (if they are equal) don't log an activity at all.
    changes = list(itertools.islice(pillar.api.utils.doc_diff(job, original), 2))
    if not changes:
        log.info('Not registering replacement of job %s, as it is identical '
                 'in non-private fields.', job['_id'])
        return

    if len(changes) == 1:
        (key, val_job, _) = changes[0]
        human_key = pillar.web.jinja.format_undertitle(key.rsplit('.', 1)[-1])
        descr = None

        # Some key- and value-specific overrides
        if val_job is pillar.api.utils.DoesNotExist:
            descr = 'removed "%s" from shot "%s"' % (human_key, job['name'])
        elif key == 'properties.status':
            val_job = pillar.web.jinja.format_undertitle(val_job)
        elif key == 'properties.assigned_to.users':
            human_key = 'assigned users'
            val_job = get_user_list(val_job)
            descr = 'assigned job "%s" to %s' % (job['name'], val_job)
        elif isinstance(val_job, basestring) and len(val_job) > 80:
            val_job = val_job[:80] + u'…'

        if descr is None:
            descr = 'changed %s to "%s" in job "%s"' % (human_key, val_job, job['name'])
    else:
        descr = 'edited job "%s"' % job['name']

    register_job_activity(job, descr)


@only_for_job
def activity_after_creating_job(job):
    register_job_activity(job, 'created a new job "%s"' % job['name'])


def activity_after_creating_jobs(nodes):
    for node in nodes:
        activity_after_creating_job(node)


@only_for_job
def activity_after_deleting_job(job):
    register_job_activity(job, 'deleted job "%s"' % job['name'])


@only_for_job
def create_shortcode(job):
    from flamenco import shortcodes

    shortcode = shortcodes.generate_shortcode(job['project'], job['node_type'], u'T')
    job.setdefault('properties', {})['shortcode'] = shortcode


def create_shortcodes(nodes):
    for node in nodes:
        create_shortcode(node)


def setup_app(app):
    app.on_fetched_item_nodes += fetch_job_extra_info
    app.on_fetched_resource_nodes += fetch_jobs_parent_info

    app.on_replaced_nodes += activity_after_replacing_job
    app.on_inserted_nodes += activity_after_creating_jobs
    app.on_insert_nodes += create_shortcodes
    app.on_deleted_item_nodes += activity_after_deleting_job
    app.on_deleted_resource_nodes += activity_after_deleting_job
