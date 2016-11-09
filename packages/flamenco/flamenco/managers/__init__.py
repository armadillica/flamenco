"""Manager management."""

import attr
import flask
import flask_login

import pillarsdk
from pillar import attrs_extra
from pillar.api.activities import register_activity
from pillar.web.system_util import pillar_api
from pillar.api.utils import authentication

from flamenco.node_types.manager import node_type_manager


@attr.s
class ManagerManager(object):
    _log = attrs_extra.log('%s.ManagerManager' % __name__)

    def create_manager(self, project, manager_type=None, parent=None):
        """Creates a new manager, owned by the current user.

        :rtype: pillarsdk.Node
        """

        from pillar.web.jinja import format_undertitle

        api = pillar_api()
        node_type = project.get_node_type(node_type_manager['name'])
        if not node_type:
            raise ValueError('Project %s not set up for Flamenco' % project._id)

        node_props = dict(
            name='New manager',
            project=project['_id'],
            user=flask_login.current_user.objectid,
            node_type=node_type['name'],
            properties={
                'status': node_type['dyn_schema']['status']['default'],
            },
        )

        if manager_type:
            node_props['name'] = format_undertitle(manager_type)
            node_props['properties']['manager_type'] = manager_type
        if parent:
            node_props['parent'] = parent

        manager = pillarsdk.Node(node_props)
        manager.create(api=api)
        return manager

    def edit_manager(self, manager_id, **fields):
        """Edits a manager.

        :type manager_id: str
        :type fields: dict
        :rtype: pillarsdk.Node
        """

        api = pillar_api()
        manager = pillarsdk.Node.find(manager_id, api=api)

        manager._etag = fields.pop('_etag')
        manager.name = fields.pop('name')
        manager.description = fields.pop('description')
        manager.properties.status = fields.pop('status')
        manager.properties.manager_type = fields.pop('manager_type', '').strip() or None

        users = fields.pop('users', None)
        manager.properties.assigned_to = {'users': users or []}

        self._log.info('Saving manager %s', manager.to_dict())

        if fields:
            self._log.warning('edit_manager(%r, ...) called with unknown fields %r; ignoring them.',
                              manager_id, fields)

        manager.update(api=api)
        return manager

    def delete_manager(self, manager_id, etag):
        api = pillar_api()

        self._log.info('Deleting manager %s', manager_id)
        manager = pillarsdk.Node({'_id': manager_id, '_etag': etag})
        manager.delete(api=api)

    def managers_for_user(self, user_id):
        """Returns the managers for the given user.

        :returns: {'_items': [manager, manager, ...], '_meta': {Eve metadata}}
        """

        api = pillar_api()

        # TODO: also include managers assigned to any of the user's groups.
        managers = pillarsdk.Node.all({
            'where': {
                'properties.assigned_to.users': user_id,
                'node_type': node_type_manager['name'],
            }
        }, api=api)

        return managers

    def managers_for_project(self, project_id):
        """Returns the managers for the given project.

        :returns: {'_items': [manager, manager, ...], '_meta': {Eve metadata}}
        """

        api = pillar_api()
        managers = pillarsdk.Node.all({
            'where': {
                'project': project_id,
                'node_type': node_type_manager['name'],
            }}, api=api)
        return managers

    def api_manager_for_shortcode(self, shortcode):
        """Returns the manager for the given shortcode.

        :returns: the manager Node, or None if not found.
        """

        db = flask.current_app.db()
        manager = db['nodes'].find_one({
            'properties.shortcode': shortcode,
            'node_type': node_type_manager['name'],
        })

        return manager


def setup_app(app):
    from . import eve_hooks

    eve_hooks.setup_app(app)
