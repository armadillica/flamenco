import typing

import bson

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class JobRecreationTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        super().setUp(**kwargs)

        from pillar.api.utils.authentication import force_cli_user

        self.manager, _, _ = self.create_manager_service_account(
            assign_to_project_id=self.proj_id)

        with self.app.test_request_context():
            force_cli_user()
            job_doc = self.jmngr.api_create_job(
                'test job',
                'Wörk wørk w°rk.',
                'sleep',
                {
                    'frames': '12-18, 20-22',
                    'chunk_size': 5,
                    'time_in_seconds': 3,
                },
                self.proj_id,
                ctd.EXAMPLE_PROJECT_OWNER_ID,
                self.manager['_id'],
            )

            self.job_id = job_doc['_id']

    def test_recreate_job__not_canceled(self):
        # The job should fail, as it was created in 'queued' state.
        with self.app.test_request_context():
            self.assertRaises(ValueError, self.flamenco.api_recreate_job, self.job_id)

    def _pre_test(self) -> typing.Set[bson.ObjectId]:
        with self.app.test_request_context():
            # Cancel the job & its tasks.
            self.jmngr.api_set_job_status(self.job_id, 'canceled')
            self.tmngr.api_set_task_status_for_job(self.job_id, 'queued', 'canceled')

            # Get the list of original task IDs so we can check they're not re-used later.
            tcoll = self.flamenco.db('tasks')
            old_task_ids = {t['_id'] for t in tcoll.find({'job': self.job_id})}

        return old_task_ids

    def _post_test(self, old_task_ids):
        with self.app.test_request_context():
            tcoll = self.flamenco.db('tasks')

            new_tasks = list(tcoll.find({'job': self.job_id}))
            new_task_ids = {t['_id'] for t in new_tasks}

            # The job hasn't changed, so the number of tasks should remain the same.
            self.assertEqual(len(old_task_ids), len(new_task_ids))

            # Tasks should not be re-used.
            self.assertFalse(new_task_ids.intersection(old_task_ids))

            # The job and all new tasks should be set to 'queued'.
            jcoll = self.flamenco.db('jobs')
            new_job = jcoll.find_one(self.job_id)
            self.assertEqual('queued', new_job['status'])
            self.assertEqual(len(new_task_ids) * ['queued'], [t['status'] for t in new_tasks])

    def test_recreate_job(self):
        from pillar.api.utils.authentication import force_cli_user

        old_task_ids = self._pre_test()

        with self.app.test_request_context():
            # Recreate the job, and check the task statuses.
            force_cli_user()
            self.flamenco.api_recreate_job(self.job_id)

        self._post_test(old_task_ids)

    def test_recreate_job_as_project_member(self):
        from pillar.api.projects.utils import get_admin_group_id
        import pillar.auth
        from flamenco.jobs import routes

        with self.app.test_request_context():
            groups = self.create_standard_groups()
            admin_gid = get_admin_group_id(self.proj_id)

        self.create_user(24 * 'd',
                         roles={'subscriber', 'flamenco-user'},
                         groups=[groups['subscriber'], admin_gid],
                         token='user-token')

        old_task_ids = self._pre_test()

        # Test we're able to get the job itself.
        self.get(f'/api/flamenco/jobs/{self.job_id}', auth_token='user-token')

        # The user should also be allowed to recreate the job.
        with self.app.test_request_context():
            pillar.auth.login_user('user-token', load_from_db=True)
            routes.recreate_job(self.project['url'], self.job_id)

        self._post_test(old_task_ids)
