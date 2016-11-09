from flask import url_for

from pillar.web.nodes.finders import register_node_finder

from flamenco.node_types.job import node_type_job
from flamenco.node_types.manager import node_type_manager
from flamenco.node_types.task import node_type_task


@register_node_finder(node_type_job['name'])
def find_for_job(project, node):
    return url_for('flamenco.jobs.perproject.view_job',
                   project_url=project['url'],
                   job_id=node['_id'])


@register_node_finder(node_type_manager['name'])
def find_for_manager(project, node):
    return url_for('flamenco.managers.perproject.view_manager',
                   project_url=project['url'],
                   manager_id=node['_id'])


@register_node_finder(node_type_task['name'])
def find_for_task(project, node):
    endpoint = 'flamenco.tasks.perproject.view_task'
    return url_for(endpoint, project_url=project['url'], task_id=node['_id'])
