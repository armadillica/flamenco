"""Task management."""

import attr
import flask
import flask_login

import pillarsdk
from pillar import attrs_extra
from pillar.api.activities import register_activity
from pillar.web.system_util import pillar_api
from pillar.api.utils import authentication

from attract.node_types.task import node_type_task


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
            raise ValueError('Project %s not set up for Attract' % project._id)

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

    def api_task_logged_in_svn(self, sender, shortcode, log_entry):
        """Blinker signal receiver; connects the logged commit with the task.

        :param sender: sender of the signal
        :type sender: attract_server.subversion.CommitLogObserver
        :type log_entry: attract.subversion.LogEntry
        """

        self._log.info(u"Task '%s' logged in SVN by %s: %s...",
                       shortcode, log_entry.author, log_entry.msg[:30].replace('\n', ' // '))

        # Find the task
        task = self.api_task_for_shortcode(shortcode)
        if not task:
            self._log.warning(u'Task %s not found, ignoring SVN commit.', shortcode)
            return

        # Find the author
        db = flask.current_app.db()
        proj = db['projects'].find_one({'_id': task['project']},
                                      projection={'extension_props.attract': 1})
        if not proj:
            self._log.warning(u'Project %s for task %s not found, ignoring SVN commit.',
                              task['project'], task['_id'])
            return

        # We have to have a user ID to register an activity, which is why we fall back
        # to the current user (the SVNer service account) if there is no mapping.
        usermap = proj['extension_props'].get('attract', {}).get('svn_usermap', {})
        user_id = usermap.get(log_entry.author, None)
        msg = 'committed SVN revision %s' % log_entry.revision
        if not user_id:
            self._log.warning(u'No Pillar user mapped for SVN user %s, using SVNer account.',
                              log_entry.author)
            user_id = authentication.current_user_id()
            msg = 'committed SVN revision %s authored by SVN user %s' % (
                log_entry.revision, log_entry.author)

        register_activity(
            user_id, msg,
            'node', task['_id'],
            'node', task['parent'] or task['_id'],
            project_id=task['project'])


def setup_app(app):
    from . import eve_hooks

    eve_hooks.setup_app(app)
