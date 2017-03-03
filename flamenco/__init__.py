import logging
import os.path

import flask
from werkzeug.local import LocalProxy
from pillar.extension import PillarExtension

EXTENSION_NAME = 'flamenco'

# Roles required to view job, manager or task details.
ROLES_REQUIRED_TO_VIEW_ITEMS = {u'demo', u'subscriber', u'admin', u'flamenco-admin'}
ROLES_REQUIRED_TO_VIEW_LOGS = {u'admin', u'flamenco-admin'}


class FlamencoExtension(PillarExtension):
    def __init__(self):
        self._log = logging.getLogger('%s.FlamencoExtension' % __name__)

        import flamenco.jobs
        import flamenco.tasks
        import flamenco.managers

        self.job_manager = flamenco.jobs.JobManager()
        self.task_manager = flamenco.tasks.TaskManager()
        self.manager_manager = flamenco.managers.ManagerManager()

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

        return [
            routes.blueprint,
            flamenco.jobs.routes.perproject_blueprint,
            flamenco.jobs.routes.blueprint,
            flamenco.tasks.routes.perjob_blueprint,
            flamenco.tasks.routes.perproject_blueprint,
        ]

    @property
    def template_path(self):
        return os.path.join(os.path.dirname(__file__), 'templates')

    @property
    def static_path(self):
        return os.path.join(os.path.dirname(__file__), 'static')

    def setup_app(self, app):
        """Connects Blinker signals and sets up other app-dependent stuff in
        submodules.
        """

        # Create the flamenco_task_logs collection with a compressing storage engine.
        # If the zlib compression is too CPU-intensive, switch to Snappy instead.
        with app.app_context():
            self._create_collections(app.db())

        from . import managers, jobs, tasks

        managers.setup_app(app)
        jobs.setup_app(app)
        tasks.setup_app(app)

    def _create_collections(self, db):
        import pymongo

        # flamenco_task_logs
        if 'flamenco_task_logs' not in db.collection_names(include_system_collections=False):
            self._log.info('Creating flamenco_task_logs collection.')
            db.create_collection('flamenco_task_logs',
                                 storageEngine={
                                     'wiredTiger': {'configString': 'block_compressor=zlib'}
                                 })
        else:
            self._log.debug('Not creating flamenco_task_logs collection, already exists.')

        self._log.info('Creating index on flamenco_task_logs collection')
        db.flamenco_task_logs.create_index(
            [('task_id', pymongo.ASCENDING),
             ('received_on_manager', pymongo.ASCENDING)],
            background=True,
            unique=False,
            sparse=False,
        )

        # flamenco_tasks
        if 'flamenco_tasks' not in db.collection_names(include_system_collections=False):
            self._log.info('Creating flamenco_tasks collection.')
            db.create_collection('flamenco_tasks',
                                 storageEngine={
                                     'wiredTiger': {'configString': 'block_compressor=zlib'}
                                 })
        else:
            self._log.debug('Not creating flamenco_tasks collection, already exists.')

        self._log.info('Creating index on flamenco_tasks collection')
        db.flamenco_tasks.create_index(
            [('manager', pymongo.ASCENDING)],
            background=False,
            unique=False,
            sparse=False,
        )
        db.flamenco_tasks.create_index(
            [('_updated', pymongo.DESCENDING)],
            background=False,
            unique=False,
            sparse=False,
        )

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

        Requires Flamenco extension properties.
        """

        if not test_extension_props:
            return True

        if not project.extension_props:
            return False

        try:
            pprops = project.extension_props[EXTENSION_NAME]
        except AttributeError:
            self._log.warning("is_flamenco_project: Project url=%r doesn't have"
                              " any extension properties.", project['url'])
            if self._log.isEnabledFor(logging.DEBUG):
                import pprint
                self._log.debug('Project: %s', pprint.pformat(project.to_dict()))
            return False
        except KeyError:
            return False

        if pprops is None:
            self._log.warning("is_flamenco_project: Project url=%r doesn't have"
                              " Flamenco extension properties.", project['url'])
            return False
        return True

    def current_user_is_flamenco_admin(self):
        """Returns True iff the user is a Flamenco admin or regular admin."""

        from pillar.api.utils.authorization import user_matches_roles

        return user_matches_roles({u'admin', u'flamenco-admin'})

    def sidebar_links(self, project):

        if not self.is_flamenco_project(project):
            return ''

        # Temporarily disabled until Flamenco is nicer to look at.
        return ''
        # return flask.render_template('flamenco/sidebar.html',
        #                              project=project)

    def db(self, collection_name):
        """Returns a Flamenco-specific MongoDB collection."""
        return flask.current_app.db()['flamenco_%s' % collection_name]

    def update_status(self, collection_name, document_id, new_status):
        """Updates a document's status, avoiding Eve.

        Doesn't use Eve patch_internal to avoid Eve's authorisation. For
        example, Eve doesn't know certain PATCH operations are allowed by
        Flamenco managers.

        :rtype: pymongo.results.UpdateResult
        """

        return self.update_status_q(collection_name, {'_id': document_id}, new_status)

    def update_status_q(self, collection_name, query, new_status):
        """Updates the status for the queried objects.

        :returns: the result of the collection.update_many() call
        :rtype: pymongo.results.UpdateResult
        """
        from flamenco import eve_settings, current_flamenco
        import datetime
        import uuid
        from bson import tz_util

        singular_name = collection_name.rstrip('s')  # jobs -> job
        schema = eve_settings.DOMAIN['flamenco_%s' % collection_name]['schema']
        valid_statuses = schema['status']['allowed']

        if new_status not in valid_statuses:
            raise ValueError('Invalid %s status %s' % (singular_name, new_status))

        # Generate random ETag since we can't compute it from the entire document.
        # This means that a subsequent PUT will change the etag even when the document doesn't
        # change; this is unavoidable without fetching the entire document.
        etag = uuid.uuid4().hex

        collection = current_flamenco.db(collection_name)
        result = collection.update_many(
            query,
            {'$set': {'status': new_status,
                      '_updated': datetime.datetime.now(tz=tz_util.utc),
                      '_etag': etag}}
        )

        self._log.debug('Updated status of %i %s %s to %s',
                        result.modified_count, singular_name, query, new_status)

        return result


def _get_current_flamenco():
    """Returns the Flamenco extension of the current application."""

    return flask.current_app.pillar_extensions[EXTENSION_NAME]


current_flamenco = LocalProxy(_get_current_flamenco)
"""Flamenco extension of the current app."""
