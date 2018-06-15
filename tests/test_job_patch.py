# -*- encoding: utf-8 -*-

import mock

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class JobPatchingTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user
        from pillar.api.projects.utils import get_admin_group_id

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']
        self.mngr_token = token['token']

        self.assign_manager_to_project(self.mngr_id, self.proj_id)

        with self.app.test_request_context():
            group_id = get_admin_group_id(self.proj_id)

        self.create_user(user_id=24 * 'f', roles={'flamenco-admin'}, groups=[group_id])
        self.create_valid_auth_token(24 * 'f', 'fladmin-token')

        with self.app.test_request_context():
            force_cli_user()
            job = self.jmngr.api_create_job(
                'test job',
                'Wörk wørk w°rk.',
                'sleep',
                {
                    'frames': '12-18, 20-22',
                    'chunk_size': 3,
                    'time_in_seconds': 3,
                },
                self.proj_id,
                ctd.EXAMPLE_PROJECT_OWNER_ID,
                self.mngr_id,
            )
            self.job_id = job['_id']

    def test_set_job_invalid_status(self):
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'set-job-status',
                  'status': 'finished'},
            auth_token='fladmin-token',
            expected_status=422,
        )

        # Check that the status in the database didn't change.
        with self.app.test_request_context():
            jobs_coll = self.flamenco.db('jobs')
            job = jobs_coll.find_one({'_id': self.job_id})
            self.assertEqual('queued', job['status'])

    def test_set_job_valid_status(self):
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'set-job-status',
                  'status': 'completed'},
            auth_token='fladmin-token',
            expected_status=204,
        )

        # Check that the status in the database changed too.
        with self.app.test_request_context():
            jobs_coll = self.flamenco.db('jobs')
            job = jobs_coll.find_one({'_id': self.job_id})
            self.assertEqual('completed', job['status'])

    @mock.patch('flamenco.jobs.JobManager.handle_job_status_change')
    def test_task_status_change_due_to_job_patch(self, mock_handle_job_status_change):
        self.assert_job_status('queued')

        mock_handle_job_status_change.return_value = None
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'set-job-status',
                  'status': 'completed'},
            auth_token='fladmin-token',
            expected_status=204,
        )

        mock_handle_job_status_change.assert_called_with(
            self.job_id, 'queued', 'completed')
        self.assert_job_status('completed')

    @mock.patch('flamenco.jobs.JobManager.handle_job_status_change')
    def test_set_job_valid_status_as_outside_subscriber(self, mock_handle_job_status_change):
        """Flamenco users not member of the project should not be allowed to do this."""

        self.create_user(user_id=24 * 'e', roles={'subscriber'},
                         token='flamuser-token')

        self.assert_job_status('queued')
        mock_handle_job_status_change.return_value = None
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'set-job-status',
                  'status': 'completed'},
            auth_token='flamuser-token',
            expected_status=403,
        )

        mock_handle_job_status_change.assert_not_called()
        self.assert_job_status('queued')

    @mock.patch('flamenco.jobs.JobManager.handle_job_status_change')
    def test_set_job_valid_status_as_projmember_subscriber(self, mock_handle_job_status_change):
        """Subscribers member of the project should be allowed to do this."""

        from pillar.api.projects.utils import get_admin_group_id

        with self.app.test_request_context():
            admin_group_id = get_admin_group_id(self.proj_id)

        self.create_user(user_id=24 * 'e', roles={'subscriber'},
                         groups=[admin_group_id],
                         token='flamuser-token')

        self.assert_job_status('queued')
        mock_handle_job_status_change.return_value = None
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'set-job-status',
                  'status': 'completed'},
            auth_token='flamuser-token',
            expected_status=204,
        )

        mock_handle_job_status_change.assert_called_with(
            self.job_id, 'queued', 'completed')
        self.assert_job_status('completed')

    @mock.patch('flamenco.tasks.TaskManager.api_set_task_status_for_job')
    def test_requeue_failed_tasks(self, mock_api_set_task_status_for_job):
        self.force_job_status('active')

        mock_api_set_task_status_for_job.return_value = None
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'requeue-failed-tasks'},
            auth_token='fladmin-token',
            expected_status=204,
        )

        mock_api_set_task_status_for_job.assert_called_with(
            self.job_id, from_status='failed', to_status='queued')
        self.assert_job_status('active')
