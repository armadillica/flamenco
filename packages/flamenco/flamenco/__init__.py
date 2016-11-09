import logging

import flask
from werkzeug.local import LocalProxy
from pillar.extension import PillarExtension
import pillar.web.subquery
from pillar.web.system_util import pillar_api
from pillar.web.nodes.routes import url_for_node

import pillarsdk

import flamenco.jobs
import flamenco.managers
import flamenco.tasks

EXTENSION_NAME = 'flamenco'

# Roles required to view job, manager or task details.
ROLES_REQUIRED_TO_VIEW_ITEMS = {u'demo', u'subscriber', u'admin'}


class FlamencoExtension(PillarExtension):
    def __init__(self):
        self._log = logging.getLogger('%s.FlamencoExtension' % __name__)
        self.job_manager = flamenco.jobs.JobManager()
        self.manager_manager = flamenco.managers.ManagerManager()
        self.task_manager = flamenco.tasks.TaskManager()

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
        import flamenco.jobs.routes
        import flamenco.managers.routes
        import flamenco.tasks.routes

        return [
            routes.blueprint,
            flamenco.jobs.routes.blueprint,
            flamenco.jobs.routes.perproject_blueprint,
            flamenco.managers.routes.blueprint,
            flamenco.managers.routes.perproject_blueprint,
            flamenco.tasks.routes.blueprint,
            flamenco.tasks.routes.perproject_blueprint,
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

        from . import comments, jobs, managers, tasks, eve_hooks

        comments.setup_app(app)
        jobs.setup_app(app)
        managers.setup_app(app)
        tasks.setup_app(app)
        eve_hooks.setup_app(app)

        # Imports for side-effects
        from . import node_url_finders

    def flamenco_projects(self):
        """Returns projects set up for Flamenco.

        :returns: {'_items': [proj, proj, ...], '_meta': Eve metadata}
        """

        import pillarsdk
        from pillar.web.system_util import pillar_api

        api = pillar_api()

        # Find projects that are set up for Flamenco.
        projects = pillarsdk.Project.all({
            'where': {
                'extension_props.flamenco': {'$exists': 1},
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
        """Returns a page of activities for the given job, manager or task.

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

        from .node_types.job import node_type_job
        from .node_types.manager import node_type_manager
        from .node_types.task import node_type_task

        if act.node_type == node_type_task['name']:
            return flask.url_for('flamenco.tasks.perproject.view_task',
                                 project_url=act.project.url,
                                 task_id=act.object)

        elif act.node_type == node_type_job['name']:
            return flask.url_for('flamenco.jobs.perproject.view_job',
                                 project_url=act.project.url,
                                 job_id=act.object)

        elif act.node_type == node_type_manager['name']:
            return flask.url_for('flamenco.managers.perproject.view_manager',
                                 project_url=act.project.url,
                                 manager_id=act.object)

        return url_for_node(node_id=act.object)


def _get_current_flamenco():
    """Returns the Flamenco extension of the current application."""

    return flask.current_app.pillar_extensions[EXTENSION_NAME]


current_flamenco = LocalProxy(_get_current_flamenco)
"""Flamenco extension of the current app."""
