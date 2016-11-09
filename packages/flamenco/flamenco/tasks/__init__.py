"""Task management."""

import attr
import flask
import flask_login

import pillarsdk
from pillar import attrs_extra
from pillar.api.activities import register_activity
from pillar.web.system_util import pillar_api
from pillar.api.utils import authentication

from flamenco.node_types.task import node_type_task


@attr.s
class TaskManager(object):
    _log = attrs_extra.log('%s.TaskManager' % __name__)

    def create_task(self, project, task_type=None, parent=None):
        """Creates a new task, owned by the current user.

        :rtype: pillarsdk.Node
        """

        from pillar.web.jinja import format_undertitle

        api = pillar_api()
        node_type = project.get_node_type(node_type_task['name'])
        if not node_type:
            raise ValueError('Project %s not set up for Flamenco' % project._id)

        node_props = dict(
            name='New task',
            project=project['_id'],
            user=flask_login.current_user.objectid,
            node_type=node_type['name'],
            properties={
                'status': node_type['dyn_schema']['status']['default'],
            },
        )

        if task_type:
            node_props['name'] = format_undertitle(task_type)
            node_props['properties']['task_type'] = task_type
        if parent:
            node_props['parent'] = parent

        task = pillarsdk.Node(node_props)
        task.create(api=api)
        return task

    def edit_task(self, task_id, **fields):
        """Edits a task.

        :type task_id: str
        :type fields: dict
        :rtype: pillarsdk.Node
        """

        api = pillar_api()
        task = pillarsdk.Node.find(task_id, api=api)

        task._etag = fields.pop('_etag')
        task.name = fields.pop('name')
        task.description = fields.pop('description')
        task.properties.status = fields.pop('status')
        task.properties.task_type = fields.pop('task_type', '').strip() or None

        users = fields.pop('users', None)
        task.properties.assigned_to = {'users': users or []}

        self._log.info('Saving task %s', task.to_dict())

        if fields:
            self._log.warning('edit_task(%r, ...) called with unknown fields %r; ignoring them.',
                              task_id, fields)

        task.update(api=api)
        return task

    def delete_task(self, task_id, etag):
        api = pillar_api()

        self._log.info('Deleting task %s', task_id)
        task = pillarsdk.Node({'_id': task_id, '_etag': etag})
        task.delete(api=api)

    def tasks_for_user(self, user_id):
        """Returns the tasks for the given user.

        :returns: {'_items': [task, task, ...], '_meta': {Eve metadata}}
        """

        api = pillar_api()

        # TODO: also include tasks assigned to any of the user's groups.
        tasks = pillarsdk.Node.all({
            'where': {
                'properties.assigned_to.users': user_id,
                'node_type': node_type_task['name'],
            }
        }, api=api)

        return tasks

    def tasks_for_project(self, project_id):
        """Returns the tasks for the given project.

        :returns: {'_items': [task, task, ...], '_meta': {Eve metadata}}
        """

        api = pillar_api()
        tasks = pillarsdk.Node.all({
            'where': {
                'project': project_id,
                'node_type': node_type_task['name'],
            }}, api=api)
        return tasks

    def api_task_for_shortcode(self, shortcode):
        """Returns the task for the given shortcode.

        :returns: the task Node, or None if not found.
        """

        db = flask.current_app.db()
        task = db['nodes'].find_one({
            'properties.shortcode': shortcode,
            'node_type': node_type_task['name'],
        })

        return task


def setup_app(app):
    from . import eve_hooks

    eve_hooks.setup_app(app)
