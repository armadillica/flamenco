# -*- encoding: utf-8 -*-
from __future__ import absolute_import

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class JobManagerTest(AbstractFlamencoTest):
    def test_create_job(self):
        manager = self.create_manager()

        with self.app.test_request_context():
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
        jobs = self.get('/api/flamenco/jobs').json()
        self.assertEqual(1, jobs['_meta']['total'])
        job = jobs['_items'][0]

        self.assertEqual(u'Wörk wørk w°rk.', job['description'])
        self.assertEqual(u'sleep', job['job_type'])

        # Test the tasks
        tasks = self.get('/api/flamenco/tasks').json()
        self.assertEqual(2, tasks['_meta']['total'])

        task = tasks['_items'][0]
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
