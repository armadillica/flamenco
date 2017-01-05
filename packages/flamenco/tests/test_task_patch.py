# -*- encoding: utf-8 -*-
from __future__ import absolute_import

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

        with self.app.test_request_context():
            force_cli_user()
            self.jmngr.api_create_job(
                'test job',
                u'Wörk wørk w°rk.',
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

    def test_set_task_invalid_status(self):
        chunk = self.get('/flamenco/scheduler/tasks/%s' % self.mngr_id,
                         auth_token=self.mngr_token).json()
        task = chunk[0]
        task_url = '/api/flamenco/tasks/%s' % task['_id']

        self.patch(
            task_url,
            json={'op': 'set-task-status',
                  'status': 'finished',
                  },
            auth_token=self.mngr_token,
            expected_status=422,
        )

        # Check that the status in the database didn't change.
        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            task = tasks_coll.find_one({'_id': ObjectId(task['_id'])})
            self.assertEqual('claimed-by-manager', task['status'])

    def test_set_task_valid_status(self):
        chunk = self.get('/flamenco/scheduler/tasks/%s' % self.mngr_id,
                         auth_token=self.mngr_token).json()
        task = chunk[0]
        task_url = '/api/flamenco/tasks/%s' % task['_id']

        self.patch(
            task_url,
            json={'op': 'set-task-status',
                  'status': 'completed',
                  },
            auth_token=self.mngr_token,
            expected_status=204,
        )

        # Check that the status in the database changed too.
        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            task = tasks_coll.find_one({'_id': ObjectId(task['_id'])})
            self.assertEqual('completed', task['status'])
