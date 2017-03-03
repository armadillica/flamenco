# -*- encoding: utf-8 -*-

from bson import ObjectId

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class TaskPatchingTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']
        self.mngr_token = token['token']

        self.create_user(user_id=24 * 'f', roles={'flamenco-admin'})
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

    def test_set_task_invalid_status(self):
        chunk = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json()['depsgraph']
        task = chunk[0]
        task_url = '/api/flamenco/tasks/%s' % task['_id']

        self.patch(
            task_url,
            json={'op': 'set-task-status',
                  'status': 'finished',
                  },
            auth_token='fladmin-token',
            expected_status=422,
        )

        # Check that the status in the database didn't change.
        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            task = tasks_coll.find_one({'_id': ObjectId(task['_id'])})
            self.assertEqual('claimed-by-manager', task['status'])

    def test_set_task_valid_status(self):
        chunk = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json()['depsgraph']
        task = chunk[0]
        task_url = '/api/flamenco/tasks/%s' % task['_id']

        self.patch(
            task_url,
            json={'op': 'set-task-status',
                  'status': 'completed',
                  },
            auth_token='fladmin-token',
            expected_status=204,
        )

        # Check that the status in the database changed too.
        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            task = tasks_coll.find_one({'_id': ObjectId(task['_id'])})
            self.assertEqual('completed', task['status'])

    def test_job_status_change_due_to_task_patch(self):
        """A job should be marked as completed after all tasks are completed."""

        self.assert_job_status('queued')

        # The test job consists of 4 tasks; get their IDs through the scheduler.
        # This should set the job status to active.
        tasks = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json()['depsgraph']
        self.assertEqual(4, len(tasks))

        # After setting tasks 1-3 to 'completed' the job should still not be completed.
        for task in tasks[:-1]:
            self.patch(
                '/api/flamenco/tasks/%s' % task['_id'],
                json={'op': 'set-task-status', 'status': 'completed'},
                auth_token='fladmin-token',
                expected_status=204,
            )
        self.assert_job_status('active')

        self.patch(
            '/api/flamenco/tasks/%s' % tasks[-1]['_id'],
            json={'op': 'set-task-status', 'status': 'completed'},
            auth_token='fladmin-token',
            expected_status=204,
        )
        self.assert_job_status('completed')
