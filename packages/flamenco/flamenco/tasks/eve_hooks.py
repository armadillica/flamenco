# -*- encoding: utf-8 -*-

import logging

import itertools
from flask import current_app, g

from pillar.api.nodes import only_for_node_type_decorator
import pillar.api.activities
import pillar.api.utils.authentication
import pillar.web.jinja

from attract.node_types.task import node_type_task

log = logging.getLogger(__name__)
only_for_task = only_for_node_type_decorator(node_type_task['name'])


@only_for_task
def fetch_task_extra_info(node):
    """Extends the node with some info about its parent and project.

    This allows us to link to the shot the task is attached to.
    However, such a link requires at least knowing the parent node type,
    which we thus embed here.
    """

    fetch_task_parent_info(node)
    fetch_task_project_info(node)


def fetch_task_parent_info(node):
    """Store node parent info in node['_parent_info']."""

    parent_id = node.get('parent')
    if not parent_id:
        return

    nodes_coll = current_app.db()['nodes']
    parent = nodes_coll.find_one({'_id': parent_id},
                                 projection={'node_type': 1,
                                             'name': 1})
    if parent is None:
        log.warning("Task node %s has parent %s, but the parent doesn't exist.",
                    node['_id'], parent_id)
        return

    parent.pop('_id')  # always there, but also already included in the node.
    node['_parent_info'] = parent


def fetch_task_project_info(node):
    """Store node project info in node['_project_info']."""

    project_id = node.get('project')
    if not project_id:
        log.warning('Task node %s has no project!', node['_id'])
        return

    proj_coll = current_app.db()['projects']
    project = proj_coll.find_one({'_id': project_id},
                                 projection={'name': 1,
                                             'url': 1})
    if project is None:
        log.warning("Task node %s has project %s, but the project doesn't exist.",
                    node['_id'], project_id)
        return

    project.pop('_id')  # always there, but also already included in the node.
    node['_project_info'] = project


def fetch_tasks_parent_info(nodes):
    for node in nodes['_items']:
        fetch_task_extra_info(node)


# ### Activity logging ### #
def _parent_name(task):
    """Returns 'for shot "shotname"' if the task is attached to the shot."""

    parent = task.get('parent')
    if not parent:
        return ''

    nodes_coll = current_app.db()['nodes']
    shot = nodes_coll.find_one(parent)
    if shot:
        return ' for shot "%s"' % shot['name']

    return ''


def register_task_activity(task, descr):
    user_id = pillar.api.utils.authentication.current_user_id()

    context_ob = task.get('parent')
    context_type = 'node'
    if not context_ob:
        context_type = 'project'
        context_ob = task['project']

    pillar.api.activities.register_activity(
        user_id,
        descr + _parent_name(task),
        'node', task['_id'],
        context_type, context_ob,
        task['project'],
        node_type=task['node_type'],
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


@only_for_task
def activity_after_replacing_task(task, original):
    # Compare to original, and either mention the things that changed,
    # or (if they are equal) don't log an activity at all.
    changes = list(itertools.islice(pillar.api.utils.doc_diff(task, original), 2))
    if not changes:
        log.info('Not registering replacement of task %s, as it is identical '
                 'in non-private fields.', task['_id'])
        return

    if len(changes) == 1:
        (key, val_task, _) = changes[0]
        human_key = pillar.web.jinja.format_undertitle(key.rsplit('.', 1)[-1])
        descr = None

        # Some key- and value-specific overrides
        if val_task is pillar.api.utils.DoesNotExist:
            descr = 'removed "%s" from shot "%s"' % (human_key, task['name'])
        elif key == 'properties.status':
            val_task = pillar.web.jinja.format_undertitle(val_task)
        elif key == 'properties.assigned_to.users':
            human_key = 'assigned users'
            val_task = get_user_list(val_task)
            descr = 'assigned task "%s" to %s' % (task['name'], val_task)
        elif isinstance(val_task, basestring) and len(val_task) > 80:
            val_task = val_task[:80] + u'…'

        if descr is None:
            descr = 'changed %s to "%s" in task "%s"' % (human_key, val_task, task['name'])
    else:
        descr = 'edited task "%s"' % task['name']

    register_task_activity(task, descr)


@only_for_task
def activity_after_creating_task(task):
    register_task_activity(task, 'created a new task "%s"' % task['name'])


def activity_after_creating_tasks(nodes):
    for node in nodes:
        activity_after_creating_task(node)


@only_for_task
def activity_after_deleting_task(task):
    register_task_activity(task, 'deleted task "%s"' % task['name'])


@only_for_task
def create_shortcode(task):
    from attract import shortcodes

    shortcode = shortcodes.generate_shortcode(task['project'], task['node_type'], u'T')
    task.setdefault('properties', {})['shortcode'] = shortcode


def create_shortcodes(nodes):
    for node in nodes:
        create_shortcode(node)


def setup_app(app):
    app.on_fetched_item_nodes += fetch_task_extra_info
    app.on_fetched_resource_nodes += fetch_tasks_parent_info

    app.on_replaced_nodes += activity_after_replacing_task
    app.on_inserted_nodes += activity_after_creating_tasks
    app.on_insert_nodes += create_shortcodes
    app.on_deleted_item_nodes += activity_after_deleting_task
    app.on_deleted_resource_nodes += activity_after_deleting_task
