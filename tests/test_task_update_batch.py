# -*- encoding: utf-8 -*-

from bson import ObjectId

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class AbstractTaskBatchUpdateTest(AbstractFlamencoTest):
    TASK_COUNT = 0

    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']
        self.mngr_token = token['token']

    def do_schedule_tasks(self):
        # The test job consists of 4 tasks; get their IDs through the scheduler.
        # This should set the task status to claimed-by-manager.
        tasks = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json['depsgraph']
        # TODO: maybe claimed-by-manager?
        # self.assert_job_status('active')
        self.assertEqual(self.TASK_COUNT, len(tasks))
        return tasks

    def do_batch_update(self, tasks, task_indices, task_statuses, expect_cancel_task_ids=()):
        assert len(task_indices) == len(task_statuses)
        update_batch = [{'_id': str(ObjectId()),
                         'task_id': tasks[idx]['_id'],
                         'task_status': status}
                        for idx, status in zip(task_indices, task_statuses)
                        ]
        resp = self.post('/api/flamenco/managers/%s/task-update-batch' % self.mngr_id,
                         json=update_batch,
                         auth_token=self.mngr_token)
        resp_json = resp.get_json()

        self.assertEqual({item['_id'] for item in update_batch},
                         set(resp_json['handled_update_ids']),
                         'Expected all updates to be accepted by Flamenco 6Server')
        if expect_cancel_task_ids:
            self.assertEqual(set(expect_cancel_task_ids), set(resp_json['cancel_task_ids']))
        else:
            self.assertNotIn('cancel_task_ids', resp_json)


class TaskBatchUpdateTest(AbstractTaskBatchUpdateTest):
    TASK_COUNT = 4

    def setUp(self, **kwargs):
        AbstractTaskBatchUpdateTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user

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

    def test_set_task_update_happy(self):
        import dateutil.parser

        chunk = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json['depsgraph']
        task = chunk[0]
        etag_before = task['_etag']

        task_update_id = 24 * '0'
        resp = self.post('/api/flamenco/managers/%s/task-update-batch' % self.mngr_id,
                         auth_token=self.mngr_token,
                         json=[{
                             '_id': task_update_id,
                             'task_id': task['_id'],
                             'task_status': 'active',
                             'activity': 'testing stuff',
                             'received_on_manager': '2018-03-04T3:27:47+02:00',
                         }])

        self.assertEqual(resp.json['handled_update_ids'], [task_update_id])

        db_task = self.assert_task_status(task['_id'], 'active')
        self.assertEqual(db_task['activity'], 'testing stuff')
        self.assertEqual(db_task['_updated'],
                         dateutil.parser.parse('2018-03-04T3:27:47+02:00'))
        self.assertNotEqual(db_task['_etag'], etag_before)

    def test_set_task_invalid_status(self):
        chunk = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json['depsgraph']
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

        self.assertEqual(resp.json['handled_update_ids'], [task_update_id])

        db_task = self.assert_task_status(task['_id'], 'claimed-by-manager')
        self.assertEqual(db_task['activity'], 'testing stuff')

    def test_illegal_active_after_cancel_requested(self):
        from flamenco import current_flamenco

        chunk = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json['depsgraph']
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

        resp_json = resp.json
        self.assertEqual(resp_json['handled_update_ids'], [task_update_id])
        self.assertEqual(resp_json['cancel_task_ids'], [task['_id']])

        self.assert_task_status(task_id, 'cancel-requested')

    def test_canceled_after_cancel_requested(self):
        from flamenco import current_flamenco

        chunk = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json['depsgraph']
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
        resp_json = resp.json
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
        # tasks should be canceled. This is only true in this test because a single task is more
        # than the threshold of nr of tasks that are allowed to fail.
        self.maxDiff = None
        self.do_batch_update(
            tasks, [1], ['failed'],
            expect_cancel_task_ids={tasks[0]['_id'], tasks[2]['_id'], tasks[3]['_id']})
        self.assert_job_status('failed')

    def test_job_status_active_after_task_update(self):
        """A job should go to active when its tasks are being updated.
        """

        self.force_job_status('queued')
        tasks = self.do_schedule_tasks()

        # Any of these statuses should set the job to active.
        for status in ('active', 'completed'):
            self.force_job_status('queued')
            self.do_batch_update(tasks, [0], [status])
            self.assert_job_status('active')

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
        self.assert_job_status('queued')

        self.set_job_status('cancel-requested')

        # This should have cancel-requested the remaining tasks.
        self.assert_task_status(tasks[0]['_id'], 'canceled')
        self.assert_task_status(tasks[1]['_id'], 'canceled')
        self.assert_task_status(tasks[2]['_id'], 'canceled')
        self.assert_task_status(tasks[3]['_id'], 'canceled')

        # Without confirmation from the Manager, the job should go to canceled.
        self.assert_job_status('canceled')

    def test_nonmanager_access_fladmin(self):
        """Try sending batch updates as flamenco-admin instead of manager"""

        self.create_project_member(user_id=24 * 'f',
                                   token='fladmin-token',
                                   roles={'flamenco-admin'})
        tasks = self.do_schedule_tasks()
        task_id = tasks[0]['_id']

        self.force_task_status(task_id, 'active')

        self.post('/api/flamenco/managers/%s/task-update-batch' % self.mngr_id,
                  auth_token='fladmin-token',
                  json=[{
                      '_id': 24 * '0',
                      'task_id': task_id,
                      'task_status': 'failed',
                  }],
                  expected_status=403)

        self.assert_task_status(task_id, 'active')

    def test_task_updates_for_archived_job(self):
        """Archiving a job deletes tasks; we should accept task updates for them anyway."""

        self.enter_app_context()
        tasks = self.do_schedule_tasks()

        # Fake job archival -- the real code is too complex to call with the Celery stuff and all.
        self.force_job_status('archived')
        del_result = self.flamenco.db('tasks').delete_many({'job': self.job_id})
        self.assertEqual(len(tasks), del_result.deleted_count)

        # Perform the update -- these should be accepted.
        self.do_batch_update(tasks, [0, 1, 2], 3 * ['completed'])
        self.assert_job_status('archived')

    def test_job_status_queued_after_task_update(self):
        """A job should go to queued when its tasks are going back to claimed-by-manager.
        """

        self.force_job_status('queued')
        tasks = self.do_schedule_tasks()

        # Mimick two tasks going active, and then one-by-one being re-queued.
        self.do_batch_update(tasks, [0, 1], ['active', 'active'])
        self.assert_job_status('active')
        self.do_batch_update(tasks, [0], ['claimed-by-manager'])
        self.assert_job_status('active')
        self.do_batch_update(tasks, [1], ['claimed-by-manager'])
        self.assert_job_status('queued')

    def test_append_or_overwrite_log(self):
        chunk = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json['depsgraph']
        task = chunk[0]

        self.post('/api/flamenco/managers/%s/task-update-batch' % self.mngr_id,
                  auth_token=self.mngr_token,
                  json=[{
                      '_id': '000000000000000000000001',
                      'task_id': task['_id'],
                      'task_status': 'active',
                      'activity': 'testing stuff',
                      'received_on_manager': '2018-03-04T3:27:47+02:00',
                      'log': 'this is log line 1\nthis is log line 2\n',
                      'log_tail': 'this is log-tail line 1\nthis is log-tail line 2\n',
                  }])

        db_task = self.assert_task_status(task['_id'], 'active')
        self.assertEqual(db_task['activity'], 'testing stuff')
        self.assertEqual(db_task['log'], 'this is log-tail line 1\nthis is log-tail line 2\n')

        self.post('/api/flamenco/managers/%s/task-update-batch' % self.mngr_id,
                  auth_token=self.mngr_token,
                  json=[{
                      '_id': '000000000000000000000002',
                      'task_id': task['_id'],
                      'task_status': 'active',
                      'activity': 'testing more stuff',
                      'received_on_manager': '2018-03-04T3:27:47+02:00',
                      'log': 'this is log line 3\nthis is log line 4\n',
                      'log_tail': 'this is log-tail line 3\nthis is log-tail line 4\n',
                  }])

        db_task = self.assert_task_status(task['_id'], 'active')
        self.assertEqual(db_task['activity'], 'testing more stuff')
        self.assertEqual(db_task['log'], 'this is log-tail line 3\nthis is log-tail line 4\n')


class LargeTaskBatchUpdateTest(AbstractTaskBatchUpdateTest):
    """Similar tests to TaskBatchUpdateTest, but with a job consisting of many more tasks."""

    TASK_COUNT = 100

    def setUp(self, **kwargs):
        AbstractTaskBatchUpdateTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user

        with self.app.test_request_context():
            force_cli_user()
            job = self.jmngr.api_create_job(
                'test job',
                'Wörk wørk w°rk.',
                'sleep',
                {
                    'frames': '1-100',
                    'chunk_size': 1,
                    'time_in_seconds': 3,
                },
                self.proj_id,
                ctd.EXAMPLE_PROJECT_OWNER_ID,
                self.mngr_id,
            )
            self.job_id = job['_id']

    def test_job_status_not_failed_due_to_few_task_failures(self):
        self.force_job_status('queued')
        tasks = self.do_schedule_tasks()

        # After setting a single task to 'failed', the job should not be 'failed' yet.
        self.maxDiff = None
        self.do_batch_update(
            tasks, [1], ['failed'],
            expect_cancel_task_ids=set())
        self.assert_job_status('active')

        # After setting 8 more, job should still be 'active'
        self.do_batch_update(
            tasks, [2, 3, 4, 5, 6, 7, 8, 9], 8 * ['failed'],
            expect_cancel_task_ids=set())
        self.assert_job_status('active')

    def test_job_status_failed_due_to_many_task_failures(self):
        self.force_job_status('queued')
        tasks = self.do_schedule_tasks()

        # After setting 10 tasks to failed, job should be 'failed' and other tasks should cancel.
        self.do_batch_update(
            tasks, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 10 * ['failed'],
            expect_cancel_task_ids={t['_id'] for t in tasks[10:]})
        self.assert_job_status('failed')

    def test_job_status_failed_with_mixture_of_canceled_and_failed_tasks(self):
        self.force_job_status('queued')
        tasks = self.do_schedule_tasks()

        self.do_batch_update(
            tasks, list(range(14)), 14 * ['claimed-by-manager'])

        self.do_batch_update(
            tasks, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 10 * ['failed'],
            expect_cancel_task_ids={t['_id'] for t in tasks[10:]})
        self.assert_job_status('failed')

        self.do_batch_update(
            tasks, [10, 11, 12, 13], 4 * ['canceled'],
            expect_cancel_task_ids={t['_id'] for t in tasks[14:]})
        self.assert_job_status('failed')
