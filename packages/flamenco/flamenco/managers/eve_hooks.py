# -*- encoding: utf-8 -*-

import logging

import itertools
from flask import current_app, g

from pillar.api.nodes import only_for_node_type_decorator
import pillar.api.activities
import pillar.api.utils.authentication
import pillar.web.jinja

from flamenco.node_types.manager import node_type_manager

log = logging.getLogger(__name__)
only_for_manager = only_for_node_type_decorator(node_type_manager['name'])


@only_for_manager
def fetch_manager_extra_info(node):
    """Extends the node with some info about its parent and project.

    This allows us to link to the shot the manager is attached to.
    However, such a link requires at least knowing the parent node type,
    which we thus embed here.
    """

    fetch_manager_parent_info(node)
    fetch_manager_project_info(node)


def fetch_manager_parent_info(node):
    """Store node parent info in node['_parent_info']."""

    parent_id = node.get('parent')
    if not parent_id:
        return

    nodes_coll = current_app.db()['nodes']
    parent = nodes_coll.find_one({'_id': parent_id},
                                 projection={'node_type': 1,
                                             'name': 1})
    if parent is None:
        log.warning("Manager node %s has parent %s, but the parent doesn't exist.",
                    node['_id'], parent_id)
        return

    parent.pop('_id')  # always there, but also already included in the node.
    node['_parent_info'] = parent


def fetch_manager_project_info(node):
    """Store node project info in node['_project_info']."""

    project_id = node.get('project')
    if not project_id:
        log.warning('Manager node %s has no project!', node['_id'])
        return

    proj_coll = current_app.db()['projects']
    project = proj_coll.find_one({'_id': project_id},
                                 projection={'name': 1,
                                             'url': 1})
    if project is None:
        log.warning("Manager node %s has project %s, but the project doesn't exist.",
                    node['_id'], project_id)
        return

    project.pop('_id')  # always there, but also already included in the node.
    node['_project_info'] = project


def fetch_managers_parent_info(nodes):
    for node in nodes['_items']:
        fetch_manager_extra_info(node)


# ### Activity logging ### #
def _parent_name(manager):
    """Returns 'for shot "shotname"' if the manager is attached to the shot."""

    parent = manager.get('parent')
    if not parent:
        return ''

    nodes_coll = current_app.db()['nodes']
    shot = nodes_coll.find_one(parent)
    if shot:
        return ' for shot "%s"' % shot['name']

    return ''


def register_manager_activity(manager, descr):
    user_id = pillar.api.utils.authentication.current_user_id()

    context_ob = manager.get('parent')
    context_type = 'node'
    if not context_ob:
        context_type = 'project'
        context_ob = manager['project']

    pillar.api.activities.register_activity(
        user_id,
        descr + _parent_name(manager),
        'node', manager['_id'],
        context_type, context_ob,
        manager['project'],
        node_type=manager['node_type'],
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


@only_for_manager
def activity_after_replacing_manager(manager, original):
    # Compare to original, and either mention the things that changed,
    # or (if they are equal) don't log an activity at all.
    changes = list(itertools.islice(pillar.api.utils.doc_diff(manager, original), 2))
    if not changes:
        log.info('Not registering replacement of manager %s, as it is identical '
                 'in non-private fields.', manager['_id'])
        return

    if len(changes) == 1:
        (key, val_manager, _) = changes[0]
        human_key = pillar.web.jinja.format_undertitle(key.rsplit('.', 1)[-1])
        descr = None

        # Some key- and value-specific overrides
        if val_manager is pillar.api.utils.DoesNotExist:
            descr = 'removed "%s" from shot "%s"' % (human_key, manager['name'])
        elif key == 'properties.status':
            val_manager = pillar.web.jinja.format_undertitle(val_manager)
        elif key == 'properties.assigned_to.users':
            human_key = 'assigned users'
            val_manager = get_user_list(val_manager)
            descr = 'assigned manager "%s" to %s' % (manager['name'], val_manager)
        elif isinstance(val_manager, basestring) and len(val_manager) > 80:
            val_manager = val_manager[:80] + u'…'

        if descr is None:
            descr = 'changed %s to "%s" in manager "%s"' % (human_key, val_manager, manager['name'])
    else:
        descr = 'edited manager "%s"' % manager['name']

    register_manager_activity(manager, descr)


@only_for_manager
def activity_after_creating_manager(manager):
    register_manager_activity(manager, 'created a new manager "%s"' % manager['name'])


def activity_after_creating_managers(nodes):
    for node in nodes:
        activity_after_creating_manager(node)


@only_for_manager
def activity_after_deleting_manager(manager):
    register_manager_activity(manager, 'deleted manager "%s"' % manager['name'])


@only_for_manager
def create_shortcode(manager):
    from flamenco import shortcodes

    shortcode = shortcodes.generate_shortcode(manager['project'], manager['node_type'], u'T')
    manager.setdefault('properties', {})['shortcode'] = shortcode


def create_shortcodes(nodes):
    for node in nodes:
        create_shortcode(node)


def setup_app(app):
    app.on_fetched_item_nodes += fetch_manager_extra_info
    app.on_fetched_resource_nodes += fetch_managers_parent_info

    app.on_replaced_nodes += activity_after_replacing_manager
    app.on_inserted_nodes += activity_after_creating_managers
    app.on_insert_nodes += create_shortcodes
    app.on_deleted_item_nodes += activity_after_deleting_manager
    app.on_deleted_resource_nodes += activity_after_deleting_manager
