# -*- encoding: utf-8 -*-
from __future__ import absolute_import

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
                u'Wörk wørk w°rk.',
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

            self.assertEqual(u'Wörk wørk w°rk.', job['description'])
            self.assertEqual(u'sleep', job['job_type'])

        # Test the tasks
        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')

            tasks = list(tasks_coll.find())
            self.assertEqual(2, len(tasks))
            task = tasks[0]

            self.assertEqual(u'sleep-12-16', task['name'])
            self.assertEqual({
                u'name': u'echo',
                u'settings': {
                    u'message': u'Preparing to sleep',
                }
            }, task['commands'][0])

            self.assertEqual({
                u'name': u'sleep',
                u'settings': {
                    u'time_in_seconds': 3,
                }
            }, task['commands'][1])
