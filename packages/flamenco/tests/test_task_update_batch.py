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

        # A warning should be logged and the status should be rejected.
        # The rest of the update should be handled correctly, though.
        task_update_id = 24 * '0'
        resp = self.post('/api/flamenco/managers/%s/task-update-batch' % self.mngr_id,
                         auth_token=self.mngr_token,
                         json=[{
                             '_id': task_update_id,
                             'task_id': task['_id'],
                             'task_status': 'je-moeder',
                             'activity': 'testing stuff',
                         }])

        self.assertEqual(resp.json()['handled_update_ids'], [task_update_id])

        db_task = self.assert_task_status(task['_id'], 'claimed-by-manager')
        self.assertEqual(db_task['activity'], 'testing stuff')

    def test_illegal_active_after_cancel_requested(self):
        from flamenco import current_flamenco

        chunk = self.get('/flamenco/scheduler/tasks/%s' % self.mngr_id,
                         auth_token=self.mngr_token).json()
        task = chunk[0]

        # Request task cancellation after it was received by the manager.
        task_id = ObjectId(task['_id'])
        with self.app.test_request_context():
            current_flamenco.update_status('tasks', task_id, 'cancel-requested')

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

        self.assert_task_status(task_id, 'cancel-requested')

    def test_canceled_after_cancel_requested(self):
        from flamenco import current_flamenco

        chunk = self.get('/flamenco/scheduler/tasks/%s' % self.mngr_id,
                         auth_token=self.mngr_token).json()
        task = chunk[0]

        # Request task cancellation after it was received by the manager.
        task_id = ObjectId(task['_id'])
        with self.app.test_request_context():
            current_flamenco.update_status('tasks', task_id, 'cancel-requested')

        # The manager should be able to set the task status to 'canceled'
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
        self.assert_task_status(task_id, 'canceled')

    def test_job_status_complete_due_to_task_update(self):
        """A task update batch should influence the job status."""

        self.force_job_status('queued')
        tasks = self.do_schedule_tasks()

        # After setting tasks 0-2 to 'completed' the job should still not be completed.
        self.do_batch_update(tasks, [0, 1, 2], 3 * ['completed'])
        self.assert_job_status('active')

        # In the final batch we complete the remaining task.
        self.do_batch_update(tasks, [3], ['completed'])
        self.assert_job_status('completed')

    def test_job_status_failed_due_to_task_update(self):
        """A task update batch should influence the job status."""

        self.force_job_status('queued')
        tasks = self.do_schedule_tasks()

        # After setting a single task to 'failed', the job should be 'failed', and the remaining
        # tasks should be canceled.
        self.maxDiff = None
        self.do_batch_update(
            tasks, [1], ['failed'],
            expect_cancel_task_ids={tasks[0]['_id'], tasks[2]['_id'], tasks[3]['_id']})
        self.assert_job_status('failed')

    def test_job_status_canceled_due_to_task_update(self):
        """When the last cancel-requested task goes to canceled, a cancel-requested job should too.
        """

        self.force_job_status('queued')
        tasks = self.do_schedule_tasks()

        # We complete one task before attempting a cancel at the job level.
        self.do_batch_update(tasks, [0], ['completed'])
        self.assert_job_status('active')

        self.set_job_status('cancel-requested')

        # This should have cancel-requested the remaining tasks.
        self.assert_task_status(tasks[0]['_id'], 'completed')
        self.assert_task_status(tasks[1]['_id'], 'cancel-requested')
        self.assert_task_status(tasks[2]['_id'], 'cancel-requested')
        self.assert_task_status(tasks[3]['_id'], 'cancel-requested')

        # Once all tasks are confirmed to be canceled, the job should go to canceled too.
        self.do_batch_update(tasks, [1, 2, 3], 3 * ['canceled'])
        self.assert_job_status('canceled')

    def test_job_status_canceled_after_request_with_all_tasks_canceled(self):
        """Same as test_job_status_canceled_due_to_task_update(), except that in this test
        all tasks are in a state that can be immediately cancelled without waiting for the
        manager. As a result, there won't be any incoming task updates that trigger the
        cancel-requested to canceled state transition.
        """

        self.force_job_status('queued')
        tasks = self.do_schedule_tasks()

        # All tasks are queued when we request cancellation of the job.
        self.do_batch_update(tasks, [0, 1, 2, 3], 4 * ['queued'])
        self.assert_job_status('active')

        self.set_job_status('cancel-requested')

        # This should have cancel-requested the remaining tasks.
        self.assert_task_status(tasks[0]['_id'], 'canceled')
        self.assert_task_status(tasks[1]['_id'], 'canceled')
        self.assert_task_status(tasks[2]['_id'], 'canceled')
        self.assert_task_status(tasks[3]['_id'], 'canceled')

        # Without confirmation from the Manager, the job should go to canceled.
        self.assert_job_status('canceled')

    def do_schedule_tasks(self):
        # The test job consists of 4 tasks; get their IDs through the scheduler.
        # This should set the job status to active, and the task status to claimed-by-manager.
        tasks = self.get('/flamenco/scheduler/tasks/%s?chunk_size=1000' % self.mngr_id,
                         auth_token=self.mngr_token).json()
        self.assert_job_status('active')
        self.assertEqual(4, len(tasks))
        return tasks

    def do_batch_update(self, tasks, task_indices, task_statuses, expect_cancel_task_ids=()):
        assert len(task_indices) == len(task_statuses)
        update_batch = [{'_id': 24 * str(idx),
                         'task_id': tasks[idx]['_id'],
                         'task_status': status}
                        for idx, status in zip(task_indices, task_statuses)
                        ]
        resp = self.post('/api/flamenco/managers/%s/task-update-batch' % self.mngr_id,
                         json=update_batch,
                         auth_token=self.mngr_token)
        resp_json = resp.json()

        self.assertEqual({item['_id'] for item in update_batch},
                         set(resp_json['handled_update_ids']))
        if expect_cancel_task_ids:
            self.assertEqual(set(expect_cancel_task_ids), set(resp_json['cancel_task_ids']))
        else:
            self.assertNotIn('cancel_task_ids', resp_json)
