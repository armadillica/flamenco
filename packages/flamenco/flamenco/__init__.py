import logging

import flask
from werkzeug.local import LocalProxy
from pillar.extension import PillarExtension
import pillar.web.subquery
from pillar.web.system_util import pillar_api
from pillar.web.nodes.routes import url_for_node

import pillarsdk

import flamenco.tasks
import flamenco.shots

EXTENSION_NAME = 'flamenco'

# Roles required to view task or shot details.
ROLES_REQUIRED_TO_VIEW_ITEMS = {u'demo', u'subscriber', u'admin'}


class FlamencoExtension(PillarExtension):
    def __init__(self):
        self._log = logging.getLogger('%s.FlamencoExtension' % __name__)
        self.task_manager = flamenco.tasks.TaskManager()
        self.shot_manager = flamenco.shots.ShotManager()

    @property
    def name(self):
        return EXTENSION_NAME

    def flask_config(self):
        """Returns extension-specific defaults for the Flask configuration.

        Use this to set sensible default values for configuration settings
        introduced by the extension.

        :rtype: dict
        """

        # Just so that it registers the management commands.
        from . import cli

        return {}

    def eve_settings(self):
        """Returns extensions to the Eve settings.

        Currently only the DOMAIN key is used to insert new resources into
        Eve's configuration.

        :rtype: dict
        """

        return {}

    def blueprints(self):
        """Returns the list of top-level blueprints for the extension.

        These blueprints will be mounted at the url prefix given to
        app.load_extension().

        :rtype: list of flask.Blueprint objects.
        """

        from . import routes
        import flamenco.tasks.routes
        import flamenco.shots.routes
        import flamenco.subversion.routes

        return [
            routes.blueprint,
            flamenco.tasks.routes.blueprint,
            flamenco.tasks.routes.perproject_blueprint,
            flamenco.shots.routes.perproject_blueprint,
            flamenco.subversion.routes.blueprint,
            flamenco.subversion.routes.api_blueprint,
        ]

    @property
    def template_path(self):
        import os.path
        return os.path.join(os.path.dirname(__file__), 'templates')

    @property
    def static_path(self):
        import os.path
        return os.path.join(os.path.dirname(__file__), 'static')

    def setup_app(self, app):
        """Connects Blinker signals and sets up other app-dependent stuff in submodules."""

        from . import comments, subversion, tasks, eve_hooks, shots

        subversion.task_logged.connect(self.task_manager.api_task_logged_in_svn)
        comments.setup_app(app)
        tasks.setup_app(app)
        shots.setup_app(app)
        eve_hooks.setup_app(app)

        # Imports for side-effects
        from . import node_url_finders

    def flamenco_projects(self):
        """Returns projects set up for Flamenco.

        :returns: {'_items': [proj, proj, ...], '_meta': Eve metadata}
        """

        import pillarsdk
        from pillar.web.system_util import pillar_api
        from .node_types.shot import node_type_shot

        api = pillar_api()

        # Find projects that are set up for Flamenco.
        projects = pillarsdk.Project.all({
            'where': {
                'extension_props.flamenco': {'$exists': 1},
                'node_types.name': node_type_shot['name'],
            }}, api=api)

        return projects

    def is_flamenco_project(self, project, test_extension_props=True):
        """Returns whether the project is set up for Flamenco.

        Requires the task node type and Flamenco extension properties.
        Testing the latter can be skipped with test_extension_props=False.
        """

        from .node_types.task import node_type_task

        node_type_name = node_type_task['name']
        node_type = project.get_node_type(node_type_name)
        if not node_type:
            return False

        if not test_extension_props:
            return True

        try:
            pprops = project.extension_props[EXTENSION_NAME]
        except AttributeError:
            self._log.warning("is_flamenco_project: Project url=%r doesn't have any "
                              "extension properties.", project['url'])
            if self._log.isEnabledFor(logging.DEBUG):
                import pprint
                self._log.debug('Project: %s', pprint.pformat(project.to_dict()))
            return False

        if pprops is None:
            self._log.warning("is_flamenco_project: Project url=%r doesn't have Flamenco"
                              " extension properties.", project['url'])
            return False
        return True

    def sidebar_links(self, project):

        if not self.is_flamenco_project(project):
            return ''

        # Temporarily disabled until Flamenco is nicer to look at.
        return ''
        # return flask.render_template('flamenco/sidebar.html',
        #                              project=project)

    def activities_for_node(self, node_id, max_results=20, page=1):
        """Returns a page of activities for the given task or shot.

        Activities that are either on this node or have this node as context
        are returned.

        :returns: {'_items': [task, task, ...], '_meta': {Eve metadata}}
        """

        api = pillar_api()
        activities = pillarsdk.Activity.all({
            'where': {
                '$or': [
                    {'object_type': 'node',
                     'object': node_id},
                    {'context_object_type': 'node',
                     'context_object': node_id},
                ],
            },
            'sort': [('_created', -1)],
            'max_results': max_results,
            'page': page,
        }, api=api)

        # Fetch more info for each activity.
        for act in activities['_items']:
            act.actor_user = pillar.web.subquery.get_user_info(act.actor_user)

        return activities

    def link_for_activity(self, act):
        """Returns the URL for the activity.

        :type act: pillarsdk.Activity
        """

        from .node_types.task import node_type_task
        from .node_types.shot import node_type_shot

        if act.node_type == node_type_task['name']:
            if act.context_object:
                return flask.url_for('flamenco.shots.perproject.with_task',
                                     project_url=act.project.url,
                                     task_id=act.object)
            return flask.url_for('flamenco.tasks.perproject.view_task',
                                 project_url=act.project.url,
                                 task_id=act.object)
        elif act.node_type == node_type_shot['name']:
            return flask.url_for('flamenco.shots.perproject.view_shot',
                                 project_url=act.project.url,
                                 shot_id=act.object)

        return url_for_node(node_id=act.object)


def _get_current_flamenco():
    """Returns the Flamenco extension of the current application."""

    return flask.current_app.pillar_extensions[EXTENSION_NAME]


current_flamenco = LocalProxy(_get_current_flamenco)
"""Flamenco extension of the current app."""
