import mock

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class JobManagerTest(AbstractFlamencoTest):
    def test_create_job(self):
        from pillar.api.utils.authentication import force_cli_user

        manager, _, _ = self.create_manager_service_account()

        with self.app.test_request_context():
            force_cli_user()
            self.jmngr.api_create_job(
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
                manager['_id'],
            )

        # Test the jobs
        with self.app.test_request_context():
            jobs_coll = self.flamenco.db('jobs')

            jobs = list(jobs_coll.find())
            self.assertEqual(1, len(jobs))
            job = jobs[0]

            self.assertEqual('Wörk wørk w°rk.', job['description'])
            self.assertEqual('sleep', job['job_type'])

        # Test the tasks
        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')

            tasks = list(tasks_coll.find())
            self.assertEqual(2, len(tasks))

            statuses = [task['status'] for task in tasks]
            self.assertEqual(['queued', 'queued'], statuses)

            self.assertEqual(['sleep', 'sleep'], [task['task_type'] for task in tasks])

            task = tasks[0]

            self.assertEqual('sleep-12-16', task['name'])
            self.assertEqual({
                'name': 'echo',
                'settings': {
                    'message': 'Preparing to sleep',
                }
            }, task['commands'][0])

            self.assertEqual({
                'name': 'sleep',
                'settings': {
                    'time_in_seconds': 3,
                }
            }, task['commands'][1])


class JobStatusChangeTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        super(JobStatusChangeTest, self).setUp(**kwargs)

        # Create a job with the same number of tasks as there are task statuses.
        from pillar.api.utils.authentication import force_cli_user
        from flamenco.eve_settings import tasks_schema

        manager, _, token = self.create_manager_service_account()
        self.mngr_token = token['token']

        with self.app.test_request_context():
            force_cli_user()
            job = self.jmngr.api_create_job(
                'test job',
                'Wörk wørk w°rk.',
                'blender-render',
                {
                    'blender_cmd': '{blender}',
                    'filepath': '/my/file.blend',
                    # Frames and chunk size chosen to produce as many tasks
                    # as there are task statuses - 1 (we don't test 'under-construction')
                    'frames': '12-18, 20-29',
                    'chunk_size': 2,
                    'time_in_seconds': 3,
                    'render_output': '/not-relevant-now/####',
                },
                self.proj_id,
                ctd.EXAMPLE_PROJECT_OWNER_ID,
                manager['_id'],
            )
            self.job_id = job['_id']

            # Fetch the task IDs and set the task statuses to a fixed list.
            tasks_coll = self.flamenco.db('tasks')
            tasks = tasks_coll.find({
                'job': self.job_id,
                'name': {'$regex': '^blender-render-'},  # don't consider move-out-of-way task.
            }, projection={'_id': 1})
            self.task_ids = [task['_id'] for task in tasks]

        allowed_statuses: list = tasks_schema['status']['allowed']
        # this status should never occur after job compilation
        allowed_statuses.remove('under-construction')

        self.assertEqual(len(allowed_statuses), len(self.task_ids))
        self.force_task_status(0, 'queued')
        self.force_task_status(1, 'claimed-by-manager')
        self.force_task_status(2, 'completed')
        self.force_task_status(3, 'active')
        self.force_task_status(4, 'canceled')
        self.force_task_status(5, 'failed')
        self.force_task_status(6, 'cancel-requested')
        self.force_task_status(7, 'paused')
        self.force_task_status(8, 'soft-failed')

    def assert_task_status(self, task_idx, expected_status):
        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            task = tasks_coll.find_one({'_id': self.task_ids[task_idx]},
                                       projection={'status': 1})

        self.assertIsNotNone(task)
        self.assertEqual(task['status'], str(expected_status),
                         "Task %i:\n   has status: '%s'\n but expected: '%s'" % (
                             task_idx, task['status'], expected_status))

    def test_status_from_queued_to_active(self):
        # This shouldn't change any of the tasks.
        self.force_job_status('queued')
        self.set_job_status('active')

        self.assert_task_status(0, 'queued')  # was: queued
        self.assert_task_status(1, 'claimed-by-manager')  # was: claimed-by-manager
        self.assert_task_status(2, 'completed')  # was: completed
        self.assert_task_status(3, 'active')  # was: active
        self.assert_task_status(4, 'canceled')  # was: canceled
        self.assert_task_status(5, 'failed')  # was: failed
        self.assert_task_status(6, 'cancel-requested')  # was: cancel-requested
        self.assert_task_status(7, 'paused')  # was: paused
        self.assert_task_status(8, 'soft-failed')  # was: soft-failed

    def test_status_from_paused_to_queued(self):
        # This shouldn't change any of the tasks.
        self.force_job_status('paused')
        self.set_job_status('requeued')

        self.assert_task_status(0, 'queued')  # was: queued
        self.assert_task_status(1, 'queued')  # was: claimed-by-manager
        self.assert_task_status(2, 'completed')  # was: completed
        self.assert_task_status(3, 'queued')  # was: active
        self.assert_task_status(4, 'queued')  # was: canceled
        self.assert_task_status(5, 'queued')  # was: failed

        # Cancel-requested tasks are not allowed to be re-queued; it would create race conditions.
        self.assert_task_status(6, 'cancel-requested')  # was: cancel-requested
        self.assert_task_status(7, 'queued')  # was: paused
        self.assert_task_status(8, 'queued')  # was: soft-failed

        self.assert_job_status('queued')

    def test_status_from_active_to_cancel_requested(self):
        # This should cancel all tasks that could possibly still run.
        self.force_job_status('active')
        self.set_job_status('cancel-requested')

        self.assert_task_status(0, 'canceled')  # was: queued
        self.assert_task_status(1, 'cancel-requested')  # was: claimed-by-manager
        self.assert_task_status(2, 'completed')  # was: completed
        self.assert_task_status(3, 'cancel-requested')  # was: active
        self.assert_task_status(4, 'canceled')  # was: canceled
        self.assert_task_status(5, 'failed')  # was: failed
        self.assert_task_status(6, 'cancel-requested')  # was: cancel-requested
        self.assert_task_status(7, 'paused')  # was: paused
        self.assert_task_status(8, 'cancel-requested')  # was: soft-failed

    def test_status_from_canceled_to_queued(self):
        # This should not change any task status what so ever.
        self.force_job_status('canceled')
        self.set_job_status('queued')

        self.assert_task_status(0, 'queued')  # was: queued
        self.assert_task_status(1, 'claimed-by-manager')  # was: claimed-by-manager
        self.assert_task_status(2, 'completed')  # was: completed
        self.assert_task_status(3, 'active')  # was: active
        self.assert_task_status(4, 'canceled')  # was: canceled
        self.assert_task_status(5, 'failed')  # was: failed
        self.assert_task_status(6, 'cancel-requested')  # was: cancel-requested
        self.assert_task_status(7, 'paused')  # was: paused
        self.assert_task_status(8, 'soft-failed')  # was: soft-failed

    def test_status_from_canceled_to_requeued(self):
        # Add a list of failed workers to the failed task.
        with self.app.app_context():
            tasks_coll = self.app.db('flamenco_tasks')
            tasks_coll.update_one({'_id': self.task_ids[5]},
                                  {'$set': {
                                      'failed_by_workers': [
                                          {'id': 'je moeder',
                                           'identifier': 'op je hoofd'},
                                      ],
                                  }})

        # This should re-queue all non-completed tasks.
        self.force_job_status('canceled')
        self.set_job_status('requeued')
        self.assert_job_status('queued')

        self.assert_task_status(0, 'queued')  # was: queued
        self.assert_task_status(1, 'queued')  # was: claimed-by-manager
        self.assert_task_status(2, 'completed')  # was: completed
        self.assert_task_status(3, 'queued')  # was: active
        self.assert_task_status(4, 'queued')  # was: canceled
        self.assert_task_status(5, 'queued')  # was: failed

        # Cancel-requested tasks are not allowed to be re-queued; it would create race conditions.
        self.assert_task_status(6, 'cancel-requested')  # was: cancel-requested
        self.assert_task_status(7, 'queued')  # was: paused
        self.assert_task_status(8, 'queued')  # was: soft-failed

        self.assert_job_status('queued')

        # Check that the previously-failed task had its failed_by_workers list cleared.
        task5 = tasks_coll.find_one({'_id': self.task_ids[5]})
        self.assertNotIn('failed_by_workers', task5)

    def test_status_from_canceled_job_but_completed_tasks_to_requeued(self):
        # Force the job to be cancelled with all tasks at 'completed'.
        # This is not a state that should be possible, but if it happens,
        # the user should be able to get out of it.
        with self.app.app_context():
            # Update all tasks, including the file management task that is
            # otherwise ignored by the tests.
            tasks_coll = self.app.db('flamenco_tasks')
            tasks_coll.update_many({'job': self.job_id}, {'$set': {'status': 'completed'}})
        self.force_job_status('canceled')

        # This should re-queue all non-completed tasks, see that they are all
        # completed, and complete the job.
        self.set_job_status('requeued')
        self.assert_job_status('completed')

        for tidx in range(7):
            self.assert_task_status(tidx, 'completed')

    def test_status_from_completed_to_requeued(self):
        # This should re-queue all tasks.
        self.force_job_status('completed')
        self.set_job_status('requeued')
        self.assert_job_status('queued')

        self.assert_task_status(0, 'queued')  # was: queued
        self.assert_task_status(1, 'queued')  # was: claimed-by-manager
        self.assert_task_status(2, 'queued')  # was: completed
        self.assert_task_status(3, 'queued')  # was: active
        self.assert_task_status(4, 'queued')  # was: canceled
        self.assert_task_status(5, 'queued')  # was: failed

        # Cancel-requested tasks are not allowed to be re-queued; it would create race conditions.
        self.assert_task_status(6, 'cancel-requested')  # was: cancel-requested
        self.assert_task_status(7, 'queued')  # was: paused
        self.assert_task_status(8, 'queued')  # was: soft-failed

    def test_status_from_active_to_failed(self):
        # If the job fails, it cancels all remaining tasks.
        self.force_job_status('active')
        self.set_job_status('failed')

        self.assert_task_status(0, 'canceled')  # was: queued
        self.assert_task_status(1, 'cancel-requested')  # was: claimed-by-manager
        self.assert_task_status(2, 'completed')  # was: completed
        self.assert_task_status(3, 'cancel-requested')  # was: active
        self.assert_task_status(4, 'canceled')  # was: canceled
        self.assert_task_status(5, 'failed')  # was: failed
        self.assert_task_status(6, 'cancel-requested')  # was: cancel-requested
        self.assert_task_status(7, 'paused')  # was: paused
        self.assert_task_status(8, 'cancel-requested')  # was: soft-failed

    def test_status_from_active_to_completed(self):
        # Shouldn't do anything, as going to completed is a result of all tasks being completed.
        self.force_job_status('active')
        self.set_job_status('completed')

        self.assert_task_status(0, 'queued')  # was: queued
        self.assert_task_status(1, 'claimed-by-manager')  # was: claimed-by-manager
        self.assert_task_status(2, 'completed')  # was: completed
        self.assert_task_status(3, 'active')  # was: active
        self.assert_task_status(4, 'canceled')  # was: canceled
        self.assert_task_status(5, 'failed')  # was: failed
        self.assert_task_status(6, 'cancel-requested')  # was: cancel-requested
        self.assert_task_status(7, 'paused')  # was: paused
        self.assert_task_status(8, 'soft-failed')  # was: soft-failed

    def test_status_from_active_to_canceled(self):
        self.force_job_status('active')

        # Force any task that would ordinarily go to 'cancel-requested' to something that won't.
        self.force_task_status(1, 'queued')  # was: claimed-by-manager
        self.force_task_status(3, 'completed')  # was: active
        self.force_task_status(6, 'failed')  # was: cancel-requested
        self.force_task_status(8, 'failed')  # was: soft-failed

        # This should immediately go to canceled, since
        # there are no tasks to request cancellation of.
        self.set_job_status('cancel-requested')

        self.assert_task_status(0, 'canceled')  # was: queued
        self.assert_task_status(1, 'canceled')  # was: also queued
        self.assert_task_status(2, 'completed')  # was: completed
        self.assert_task_status(3, 'completed')  # was: also completed
        self.assert_task_status(4, 'canceled')  # was: canceled
        self.assert_task_status(5, 'failed')  # was: failed
        self.assert_task_status(6, 'failed')  # was: also failed
        self.assert_task_status(7, 'paused')  # was: paused
        self.assert_task_status(8, 'failed')  # was: also failed

        self.assert_job_status('canceled')

    @mock.patch('flamenco.jobs.JobManager.handle_job_status_change')
    def test_put_job(self, handle_job_status_change):
        """Test that flamenco.jobs.JobManager.handle_job_status_change is called when we PUT."""

        from pillar.api.utils import remove_private_keys

        self.create_user(24 * 'a',
                         roles={'admin', 'flamenco-admin'},
                         token='fladmin-token')

        json_job = self.get('/api/flamenco/jobs/%s' % self.job_id,
                            auth_token='fladmin-token').json

        json_job['status'] = 'canceled'

        self.put('/api/flamenco/jobs/%s' % self.job_id,
                 json=remove_private_keys(json_job),
                 headers={'If-Match': json_job['_etag']},
                 auth_token='fladmin-token')

        handle_job_status_change.assert_called_once_with(self.job_id, 'queued', 'canceled')
