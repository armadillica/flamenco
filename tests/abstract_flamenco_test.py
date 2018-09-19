# -*- encoding: utf-8 -*-

import pillarsdk
import pillar.tests
import pillar.auth

from bson import ObjectId

from pillar.tests import PillarTestServer, AbstractPillarTest
from pillar.tests import common_test_data as ctd

DEFAULT_OWNER_EMAIL = 'owner@example.com'


class FlamencoTestServer(PillarTestServer):
    def __init__(self, *args, **kwargs):
        PillarTestServer.__init__(self, *args, **kwargs)

        from flamenco import FlamencoExtension
        self.load_extension(FlamencoExtension(), '/flamenco')


class AbstractFlamencoTest(AbstractPillarTest):
    pillar_server_class = FlamencoTestServer

    def setUp(self, **kwargs):
        super().setUp(**kwargs)

        from flamenco.tasks import TaskManager
        from flamenco.jobs import JobManager

        self.tmngr: TaskManager = self.flamenco.task_manager
        self.jmngr: JobManager = self.flamenco.job_manager

        self.proj_id, self.project = self.ensure_project_exists()

        self.sdk_project = pillarsdk.Project(pillar.tests.mongo_to_sdk(self.project))

        # Set these in a subclass.
        self.task_ids = []
        self.job_id = None

    def tearDown(self):
        self.unload_modules('flamenco')
        super().tearDown()

    @property
    def flamenco(self):
        from flamenco import FlamencoExtension

        flamenco: FlamencoExtension = self.app.pillar_extensions['flamenco']
        return flamenco

    def ensure_project_exists(self, project_overrides=None):
        from flamenco.setup import setup_for_flamenco
        from pillar.api.utils.authentication import force_cli_user

        project_overrides = dict(
            picture_header=None,
            picture_square=None,
            **(project_overrides or {})
        )
        proj_id, project = AbstractPillarTest.ensure_project_exists(
            self, project_overrides)

        with self.app.test_request_context():
            force_cli_user()
            flamenco_project = setup_for_flamenco(
                project['url'], replace=True)

        return proj_id, flamenco_project

    def create_manager_service_account(
            self,
            owner_email=ctd.EXAMPLE_USER['email'],
            name='tēst mānēgūr',
            *,
            assign_to_project_id: ObjectId=None):
        from flamenco.setup import create_manager
        from pillar.api.utils.authentication import force_cli_user

        # Main project will have a manager, job, and tasks.
        with self.app.test_request_context():
            force_cli_user()

            # Make sure there is an owner for this manager.
            users_coll = self.app.db('users')
            count = users_coll.find({'email': owner_email}).count()
            if count == 0:
                self.create_user(user_id=ObjectId(), email=owner_email)
            elif count > 1:
                self.fail(f'Found {count} users with email address {owner_email}')

            mngr_doc, account, token = create_manager(owner_email, name, 'descr')

            if assign_to_project_id:
                self.assign_manager_to_project(mngr_doc['_id'], assign_to_project_id)

        return mngr_doc, account, token

    def create_project_member(self, user_id: str, *,
                              token: str,
                              roles: set = frozenset({'subscriber'}),
                              groups: list = None,
                              project: dict = None):
        """Creates a subscriber who is member of the project."""

        if project is None:
            project = self.project

        user_groups = (groups or []) + [project['permissions']['groups'][0]['group']]
        self.create_user(user_id=user_id, roles=set(roles),
                         groups=user_groups,
                         token=token)

    def assert_job_status(self, expected_status):
        with self.app.test_request_context():
            jobs_coll = self.flamenco.db('jobs')
            job = jobs_coll.find_one(self.job_id, projection={'status': 1})
        self.assertEqual(str(expected_status), job['status'])

    def set_job_status(self, new_status, job_id=None):
        """Nice, official, ripple-to-task-status approach"""

        if job_id is None:
            job_id = self.job_id

        with self.app.test_request_context():
            self.jmngr.api_set_job_status(job_id, new_status)

    def force_job_status(self, new_status, job_id=None):
        """Directly to MongoDB approach"""

        if job_id is None:
            job_id = self.job_id

        with self.app.test_request_context():
            jobs_coll = self.flamenco.db('jobs')
            result = jobs_coll.update_one({'_id': job_id},
                                          {'$set': {'status': new_status}})
        self.assertEqual(1, result.matched_count)

    def set_job_updated(self, new_updated, job_id=None):
        """Directly to MongoDB approach"""

        if job_id is None:
            job_id = self.job_id

        with self.app.app_context():
            jobs_coll = self.flamenco.db('jobs')
            result = jobs_coll.update_one({'_id': job_id},
                                          {'$set': {'_updated': new_updated}})
        self.assertEqual(1, result.matched_count)

    def assert_task_status(self, task_id, expected_status):
        if isinstance(task_id, str):
            from pillar.api.utils import str2id
            task_id = str2id(task_id)

        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            task = tasks_coll.find_one({'_id': task_id})

        self.assertIsNotNone(task, 'Task %s does not exist in the database' % task_id)
        self.assertEqual(task['status'], str(expected_status),
                         "Task %s:\n   has status: '%s'\n but expected: '%s'" % (
                             task_id, task['status'], expected_status))
        return task

    def force_task_status(self, task_idx_or_id, new_status):
        """Sets the task status directly in MongoDB.

        This should only be used to set up a certain scenario.
        """
        from flamenco import current_flamenco

        if isinstance(task_idx_or_id, ObjectId):
            task_id = task_idx_or_id
        elif isinstance(task_idx_or_id, str):
            task_id = ObjectId(task_idx_or_id)
        elif isinstance(task_idx_or_id, int):
            task_id = self.task_ids[task_idx_or_id]
        else:
            raise TypeError('task_idx_or_id can be ObjectID, str or int, not %s'
                            % type(task_idx_or_id))

        with self.app.test_request_context():
            current_flamenco.update_status('tasks', task_id, new_status)

    def assign_manager_to_project(self,
                                  manager_id: ObjectId = None,
                                  project_id: ObjectId = None):
        from flamenco import current_flamenco

        with self.app.test_request_context():
            ok = current_flamenco.manager_manager.api_assign_to_project(
                manager_id, project_id, 'assign')

        self.assertTrue(ok)

    def fetch_manager_from_db(self, manager_id: ObjectId) -> dict:
        self.assertIsInstance(manager_id, ObjectId)

        with self.app.app_context():
            managers_coll = self.app.db('flamenco_managers')
            return managers_coll.find_one(manager_id)
