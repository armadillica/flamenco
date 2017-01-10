# -*- encoding: utf-8 -*-
from __future__ import absolute_import

from bson import ObjectId

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class TaskBatchUpdateTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']
        self.mngr_token = token['token']

        with self.app.test_request_context():
            force_cli_user()
            job = self.jmngr.api_create_job(
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
            self.job_id = job['_id']

    def test_set_task_invalid_status(self):
        chunk = self.get('/flamenco/scheduler/tasks/%s' % self.mngr_id,
                         auth_token=self.mngr_token).json()
        task = chunk[0]

        # A warning should be logged, but the status change should still be accepted.
        task_update_id = 24 * '0'
        resp = self.post('/api/flamenco/managers/%s/task-update-batch' % self.mngr_id,
                  auth_token=self.mngr_token,
                  json=[{
                      '_id': task_update_id,
                      'task_id': task['_id'],
                      'task_status': 'je-moeder',
                  }])

        self.assertEqual(resp.json()['handled_update_ids'], [task_update_id])

        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            task = tasks_coll.find_one({'_id': ObjectId(task['_id'])})
        self.assertEqual('je-moeder', task['status'])

    def test_active_after_cancel_requested(self):
        from flamenco import current_flamenco

        chunk = self.get('/flamenco/scheduler/tasks/%s' % self.mngr_id,
                         auth_token=self.mngr_token).json()
        task = chunk[0]

        # Request task cancellation after it was received by the manager.
        with self.app.test_request_context():
            current_flamenco.update_status('tasks', ObjectId(task['_id']), 'cancel-requested')

        # A warning should be logged, the update should be accepted, but the status not changed.
        task_update_id = 24 * '0'
        resp = self.post('/api/flamenco/managers/%s/task-update-batch' % self.mngr_id,
                  auth_token=self.mngr_token,
                  json=[{
                      '_id': task_update_id,
                      'task_id': task['_id'],
                      'task_status': 'active',
                  }])

        resp_json = resp.json()
        self.assertEqual(resp_json['handled_update_ids'], [task_update_id])
        self.assertEqual(resp_json['cancel_task_ids'], [task['_id']])

        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            task = tasks_coll.find_one({'_id': ObjectId(task['_id'])})
        self.assertEqual('cancel-requested', task['status'])

    def test_canceled_after_cancel_requested(self):
        from flamenco import current_flamenco

        chunk = self.get('/flamenco/scheduler/tasks/%s' % self.mngr_id,
                         auth_token=self.mngr_token).json()
        task = chunk[0]

        # Request task cancellation after it was received by the manager.
        with self.app.test_request_context():
            current_flamenco.update_status('tasks', ObjectId(task['_id']), 'cancel-requested')

        # A warning should be logged, the update should be accepted, but the status not changed.
        task_update_id = 24 * '0'
        resp = self.post('/api/flamenco/managers/%s/task-update-batch' % self.mngr_id,
                  auth_token=self.mngr_token,
                  json=[{
                      '_id': task_update_id,
                      'task_id': task['_id'],
                      'task_status': 'canceled',
                  }])

        resp_json = resp.json()
        self.assertEqual(resp_json['handled_update_ids'], [task_update_id])

        # The task should no longer be cancel-requested due to the update we just pushed.
        self.assertNotIn('cancel_task_ids', resp_json)

        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            task = tasks_coll.find_one({'_id': ObjectId(task['_id'])})
        self.assertEqual('canceled', task['status'])
