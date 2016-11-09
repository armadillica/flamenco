from flask import url_for

from pillar.web.nodes.finders import register_node_finder

from flamenco.node_types.shot import node_type_shot
from flamenco.node_types.task import node_type_task


@register_node_finder(node_type_shot['name'])
def find_for_shot(project, node):
    return url_for('flamenco.shots.perproject.view_shot',
                   project_url=project['url'],
                   shot_id=node['_id'])


@register_node_finder(node_type_task['name'])
def find_for_task(project, node):

    parent = node.get(u'parent') if isinstance(node, dict) else node.parent
    if parent:
        endpoint = 'flamenco.shots.perproject.with_task'
    else:
        endpoint = 'flamenco.tasks.perproject.view_task'

    return url_for(endpoint, project_url=project['url'], task_id=node['_id'])
