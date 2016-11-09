"""Attract-wide Eve hooks."""

import logging

import flask

from pillar.api.nodes import only_for_node_type_decorator
from .node_types import NODE_TYPES

log = logging.getLogger(__name__)

attract_nodes_only = only_for_node_type_decorator(*(nt['name'] for nt in NODE_TYPES))


@attract_nodes_only
def set_default_status(node):
    """Sets the default status based on the project node type dynamic schema."""

    # FIXME: After upgrading to Eve 0.6.5 (which hopefully uses Cerberus 1.0+) this
    # should be moved to Pillar's ValidateCustomFields class. The new Cerberus should
    # (according to the docs, at least) be able to do normalisation of data based on
    # the schema. So at that point in the code, the node property and its schema are
    # already known, and we won't have to query for it again here.

    status = node.get('properties', {}).get('status', None)
    if status:
        log.debug('Node already has status=%r, not setting default', status)
        return

    proj_id = node.get('project', None)
    node_type_name = node.get('node_type', None)
    if not proj_id or not node_type_name:
        log.debug('Node %s has no project or node type, not setting status', node['_id'])
        return

    proj_coll = flask.current_app.db()['projects']
    lookup = {'_id': proj_id,
              'node_types': {'$elemMatch': {'name': node_type_name}}}

    project = proj_coll.find_one(lookup, {
        'node_types.$': 1,
    })

    schema = project['node_types'][0]['dyn_schema']
    default_status = schema['status'].get('default', None)
    if not default_status:
        log.debug('Node type %s of project %s has no default value for status property',
                  node_type_name, proj_id)
        return

    node.setdefault('properties', {})['status'] = default_status


def set_default_status_nodes(nodes):
    for node in nodes:
        set_default_status(node)


def setup_app(app):
    app.on_insert_nodes += set_default_status_nodes
