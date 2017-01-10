# -*- encoding: utf-8 -*-
from __future__ import absolute_import

from bson import ObjectId

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class TaskSchedulerTest(AbstractFlamencoTest):
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

    def _assert_sleep_task(self, expected_name, expected_status, task):
        self.assertEqual(expected_name, task['name'])
        self.assertEqual('sleep', task['job_type'])
        self.assertEqual(expected_status, task['status'])
        self.assertEqual(str(self.mngr_id), str(task['manager']))
        self.assertEqual([
            {'name': 'echo', 'settings': {'message': 'Preparing to sleep'}},
            {'name': 'sleep', 'settings': {'time_in_seconds': 3}},
        ], task['commands'])

    def test_default_chunked(self):
        from flamenco import current_flamenco

        chunk = self.get('/flamenco/scheduler/tasks/%s' % self.mngr_id,
                         auth_token=self.mngr_token).json()

        self.assertEqual(1, len(chunk))
        task = chunk[0]
        self._assert_sleep_task('sleep-12-14', 'claimed-by-manager', task)

        # Check that the status in the database changed too.
        with self.app.test_request_context():
            tasks_coll = current_flamenco.db('tasks')
            task = tasks_coll.find_one({'_id': ObjectId(task['_id'])})
            self._assert_sleep_task('sleep-12-14', 'claimed-by-manager', task)

    def test_chunked(self):
        chunk = self.get('/flamenco/scheduler/tasks/%s?chunk_size=2' % self.mngr_id,
                         auth_token=self.mngr_token).json()

        self.assertEqual(2, len(chunk))
        self._assert_sleep_task('sleep-12-14', 'claimed-by-manager', chunk[0])
        self._assert_sleep_task('sleep-15-17', 'claimed-by-manager', chunk[1])

        # Check that the last task hasn't been touched yet.
        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            task = tasks_coll.find_one({'name': 'sleep-18,20,21'})
            self._assert_sleep_task('sleep-18,20,21', 'queued', task)

    def test_by_priority(self):
        from pillar.api.utils.authentication import force_cli_user

        with self.app.test_request_context():
            force_cli_user()

            high_prio_job = self.jmngr.api_create_job(
                'test job high prio',
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
                priority=100,
            )

        high_prio_jobid = high_prio_job['_id']

        # Without proper sorting, this will return the first task, i.e. the one of the
        # medium-priority job created in setUp().
        chunk = self.get('/flamenco/scheduler/tasks/%s?chunk_size=1' % self.mngr_id,
                         auth_token=self.mngr_token).json()
        self.assertEqual(unicode(high_prio_jobid), chunk[0]['job'])

        # The task should be initialised to the job's priority.
        self.assertEqual(100, chunk[0]['priority'])
