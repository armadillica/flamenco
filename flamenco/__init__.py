import datetime
import logging
import os.path
import typing

import bson
import flask
from werkzeug.local import LocalProxy

import pillarsdk
from pillar.extension import PillarExtension

EXTENSION_NAME = 'flamenco'


class FlamencoExtension(PillarExtension):
    celery_task_modules = [
        'flamenco.celery.job_archival',
    ]
    user_roles = {
        'flamenco-admin',
        'flamenco_manager',
        'org-flamenco',
    }
    user_roles_indexable = {'org-flamenco'}

    FLAMENCO_CAPS = frozenset({'flamenco-use', 'flamenco-view', 'flamenco-view-logs'})
    user_caps = {
        'subscriber': FLAMENCO_CAPS,
        'demo': FLAMENCO_CAPS,
        'org-flamenco': FLAMENCO_CAPS,
        'flamenco-admin': FLAMENCO_CAPS | frozenset({'flamenco-admin'}),
        'admin': FLAMENCO_CAPS | frozenset({'flamenco-admin'}),
    }

    def __init__(self):
        self._log = logging.getLogger('%s.FlamencoExtension' % __name__)

        import flamenco.jobs
        import flamenco.tasks
        import flamenco.managers
        import flamenco.auth

        self.job_manager = flamenco.jobs.JobManager()
        self.task_manager = flamenco.tasks.TaskManager()
        self.manager_manager = flamenco.managers.ManagerManager()
        self.auth = flamenco.auth.Auth()

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

        return {'FLAMENCO_RESUME_ARCHIVING_AGE': datetime.timedelta(days=1)}

    def eve_settings(self):
        """Returns extensions to the Eve settings.

        Currently only the DOMAIN key is used to insert new resources into
        Eve's configuration.

        :rtype: dict
        """
        from .eve_settings import DOMAIN
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
        import flamenco.managers.routes
        import flamenco.managers.linking_routes

        return [
            routes.blueprint,
            flamenco.jobs.routes.perproject_blueprint,
            flamenco.jobs.routes.perproject_archive_blueprint,
            flamenco.jobs.routes.blueprint,
            flamenco.tasks.routes.global_blueprint,
            flamenco.tasks.routes.perjob_blueprint,
            flamenco.tasks.routes.perproject_blueprint,
            flamenco.managers.routes.blueprint,
            flamenco.managers.linking_routes.blueprint,
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
        self._setup_orphan_finder()

        # Create the flamenco_task_logs collection with a compressing storage engine.
        # If the zlib compression is too CPU-intensive, switch to Snappy instead.
        with app.app_context():
            self._create_collections(app.db())

        from . import managers, jobs, tasks

        managers.setup_app(app)
        jobs.setup_app(app)
        tasks.setup_app(app)

    def _setup_orphan_finder(self):
        """Registers a few MongoDB collections to be skipped by the orphan finder."""

        try:
            from pillar.cli.maintenance import ORPHAN_FINDER_SKIP_COLLECTIONS
        except ImportError:
            # Running on an older Pillar version without the orphan file finder.
            # In that case there is nothing for us to set up, so we can skip.
            return

        # Skipping the flamenco_task_logs collection under the assumption
        # that it does not contain any file references, and that it's too
        # big to iterate.
        ORPHAN_FINDER_SKIP_COLLECTIONS.add('flamenco_task_logs')

        # This collection doesn't link to files, and shouldn't be touched
        # by anything due to its sensitive nature.
        ORPHAN_FINDER_SKIP_COLLECTIONS.add('flamenco_manager_linking_keys')

    def _create_collections(self, db):
        import pymongo

        # flamenco_task_logs
        if 'flamenco_task_logs' not in db.list_collection_names():
            self._log.info('Creating flamenco_task_logs collection.')
            db.create_collection('flamenco_task_logs',
                                 storageEngine={
                                     'wiredTiger': {'configString': 'block_compressor=zlib'}
                                 })
        else:
            self._log.debug('Not creating flamenco_task_logs collection, already exists.')

        self._log.info('Creating index on flamenco_task_logs collection')
        db.flamenco_task_logs.create_index(
            [('task', pymongo.ASCENDING),
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

        # Manager linking keys
        if 'flamenco_manager_linking_keys' not in db.list_collection_names():
            self._log.info('Creating flamenco_manager_linking_keys collection.')
            db.create_collection('flamenco_manager_linking_keys')
        else:
            self._log.debug(
                'Not creating flamenco_manager_linking_keys collection, already exists.')

        self._log.info('Creating index on flamenco_manager_linking_keys')
        db.flamenco_manager_linking_keys.create_index('remove_after', expireAfterSeconds=0)

    def flamenco_projects(self, *, projection: dict = None):
        """Returns projects set up for Flamenco.

        :returns: {'_items': [proj, proj, ...], '_meta': Eve metadata}
        """

        import pillarsdk
        from pillar.web.system_util import pillar_api

        api = pillar_api()

        # Find projects that are set up for Flamenco.
        params = {'where': {'extension_props.flamenco': {'$exists': 1}}}
        if projection:
            params['projection'] = projection

        projects = pillarsdk.Project.all(params, api=api)
        return projects

    def is_flamenco_project(self, project: pillarsdk.Project):
        """Returns whether the project is set up for Flamenco.

        Requires Flamenco extension properties.
        """

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

    def sidebar_links(self, project):
        from pillar.api.utils import str2id

        if not self.is_flamenco_project(project):
            return ''

        project_id = str2id(project['_id'])
        if not self.auth.current_user_may(self.auth.Actions.VIEW, project_id):
            return ''

        return flask.render_template('flamenco/sidebar.html', project=project)

    @property
    def has_project_settings(self) -> bool:
        return self.auth.current_user_is_flamenco_user()

    def project_settings(self, project: pillarsdk.Project, **template_args: dict) -> flask.Response:
        """Renders the project settings page for this extension.

        Set YourExtension.has_project_settings = True and Pillar will call this function.

        :param project: the project for which to render the settings.
        :param template_args: additional template arguments.
        :returns: a Flask HTTP response
        """

        from flamenco.routes import project_settings

        return project_settings(project, **template_args)

    def db(self, collection_name):
        """Returns a Flamenco-specific MongoDB collection."""
        return flask.current_app.db()['flamenco_%s' % collection_name]

    def update_status(self, collection_name, document_id, new_status,
                      *, now: datetime.datetime = None):
        """Updates a document's status, avoiding Eve.

        Doesn't use Eve patch_internal to avoid Eve's authorisation. For
        example, Eve doesn't know certain PATCH operations are allowed by
        Flamenco managers.

        :param now: the _updated field is set to this timestamp; use this to set multiple
            objects to the same _updated field.
        :rtype: pymongo.results.UpdateResult
        """

        return self.update_status_q(collection_name, {'_id': document_id}, new_status, now=now)

    def update_status_q(self, collection_name, query, new_status, *, now: datetime.datetime = None):
        """Updates the status for the queried objects.

        :param now: the _updated field is set to this timestamp; use this to set multiple
            objects to the same _updated field.
        :returns: the result of the collection.update_many() call
        :rtype: pymongo.results.UpdateResult
        """
        from flamenco import eve_settings, current_flamenco
        import uuid

        singular_name = collection_name.rstrip('s')  # jobs -> job
        schema = eve_settings.DOMAIN['flamenco_%s' % collection_name]['schema']
        valid_statuses = schema['status']['allowed']

        if new_status not in valid_statuses:
            raise ValueError('Invalid %s status %s' % (singular_name, new_status))

        # Generate random ETag since we can't compute it from the entire document.
        # This means that a subsequent PUT will change the etag even when the document doesn't
        # change; this is unavoidable without fetching the entire document.
        etag = uuid.uuid4().hex

        if now is None:
            from bson import tz_util
            now = datetime.datetime.now(tz=tz_util.utc)

        collection = current_flamenco.db(collection_name)
        result = collection.update_many(
            query,
            {'$set': {'status': new_status,
                      '_updated': now,
                      '_etag': etag}}
        )

        self._log.debug('Updated status of %i %s %s to %s',
                        result.modified_count, singular_name, query, new_status)

        return result

    def api_recreate_job(self, job_id: bson.ObjectId):
        """Deletes all tasks of a job, then recompiles the job to construct new tasks.

        The job MUST be in state 'canceled', to ensure that the manager has stopped task execution.

        As this functionality requires access to both the task manager and the job manager,
        this is implemented on FlamencoExtension itself.
        """

        from flamenco import job_compilers
        from flamenco.jobs import RECREATABLE_JOB_STATES

        jobs_coll = current_flamenco.db('jobs')
        job_doc = jobs_coll.find_one({'_id': job_id})
        if not job_doc:
            raise ValueError('Job ID %s not found', job_id)

        if job_doc['status'] not in RECREATABLE_JOB_STATES:
            raise ValueError('Job recreation is only possible on jobs in state %s.' %
                             ', '.join(RECREATABLE_JOB_STATES))

        # Delete the tasks and revert the job to 'under-construction' status before recompiling it.
        self._log.info('Recreating job %s', job_id)
        self.job_manager.api_set_job_status(job_id, 'under-construction')
        self.task_manager.api_delete_tasks_for_job(job_id)
        job_compilers.compile_job(job_doc)
        self._log.info('Recreated job %s', job_id)


def _get_current_flamenco():
    """Returns the Flamenco extension of the current application."""

    return flask.current_app.pillar_extensions[EXTENSION_NAME]


current_flamenco: FlamencoExtension = LocalProxy(_get_current_flamenco)
"""Flamenco extension of the current app."""
