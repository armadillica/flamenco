import logging

import flask

from pillar.api.nodes import only_for_node_type_decorator
import pillar.api.activities
import pillar.api.utils.authentication

log = logging.getLogger(__name__)

comment_nodes_only = only_for_node_type_decorator('comment')


@comment_nodes_only
def activity_after_creating_node(comment):
    comment_id = comment['_id']
    parent_id = comment.get('parent', None)

    if not parent_id:
        log.warning('Comment %s created without parent.' % comment_id)
        return

    db = flask.current_app.db()
    parent = db['nodes'].find_one({'_id': parent_id},
                                  projection={'node_type': 1})
    if not parent:
        log.warning('Comment %s has non-existing parent %s' % (comment_id, parent_id))
        return

    log.debug('Recording creation of comment as activity on node %s', parent_id)

    pillar.api.activities.register_activity(
        pillar.api.utils.authentication.current_user_id(),
        'commented',
        'node', comment_id,
        'node', parent_id,
        project_id=comment.get('project', None),
        node_type=comment['node_type'],
        context_node_type=parent['node_type'],
    )


def activity_after_creating_nodes(nodes):
    for node in nodes:
        activity_after_creating_node(node)


def setup_app(app):
    app.on_inserted_nodes += activity_after_creating_nodes
