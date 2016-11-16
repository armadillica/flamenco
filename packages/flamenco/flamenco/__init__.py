import logging

import flask
from werkzeug.local import LocalProxy
from pillar.extension import PillarExtension
import pillar.web.subquery
from pillar.web.system_util import pillar_api
from pillar.web.nodes.routes import url_for_node

import pillarsdk

import flamenco.jobs
import flamenco.tasks

EXTENSION_NAME = 'flamenco'

# Roles required to view job, manager or task details.
ROLES_REQUIRED_TO_VIEW_ITEMS = {u'demo', u'subscriber', u'admin'}


class FlamencoExtension(PillarExtension):
    def __init__(self):
        self._log = logging.getLogger('%s.FlamencoExtension' % __name__)
        self.job_manager = flamenco.jobs.JobManager()
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
        from eve_settings import DOMAIN
        return {'DOMAIN': DOMAIN}

    def blueprints(self):
        """Returns the list of top-level blueprints for the extension.

        These blueprints will be mounted at the url prefix given to
        app.load_extension().

        :rtype: list of flask.Blueprint objects.
        """

        from . import routes
        import flamenco.jobs.routes
        import flamenco.tasks.routes
        import flamenco.scheduler.routes

        return [
            routes.blueprint,
            flamenco.jobs.routes.blueprint,
            flamenco.jobs.routes.perproject_blueprint,
            flamenco.tasks.routes.blueprint,
            flamenco.tasks.routes.perproject_blueprint,
            flamenco.scheduler.routes.blueprint,
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
        """Connects Blinker signals and sets up other app-dependent stuff in
        submodules.
        """

        from . import jobs, tasks, scheduler

        jobs.setup_app(app)

        # Imports for side-effects

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

    def is_flamenco_project(self, project):
        """Returns whether the project is set up for Flamenco.

        Requires Flamenco extension properties.
        """

        try:
            pprops = project.extension_props[EXTENSION_NAME]
        except AttributeError:
            self._log.warning("is_flamenco_project: Project url=%r doesn't have"
                              " any extension properties.", project['url'])
            if self._log.isEnabledFor(logging.DEBUG):
                import pprint
                self._log.debug('Project: %s', pprint.pformat(project.to_dict()))
            return False

        if pprops is None:
            self._log.warning("is_flamenco_project: Project url=%r doesn't have"
                              " Flamenco extension properties.", project['url'])
            return False
        return True

    def sidebar_links(self, project):

        if not self.is_flamenco_project(project):
            return ''

        # Temporarily disabled until Flamenco is nicer to look at.
        return ''
        # return flask.render_template('flamenco/sidebar.html',
        #                              project=project)


def _get_current_flamenco():
    """Returns the Flamenco extension of the current application."""

    return flask.current_app.pillar_extensions[EXTENSION_NAME]


current_flamenco = LocalProxy(_get_current_flamenco)
"""Flamenco extension of the current app."""
