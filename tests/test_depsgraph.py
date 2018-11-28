# -*- encoding: utf-8 -*-

import logging
import typing

from bson import ObjectId

from pillar.api.projects.utils import get_admin_group_id
from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest

log = logging.getLogger(__name__)


class DepsgraphTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user

        mngr_doc, account, token = self.create_manager_service_account(
            assign_to_project_id=self.proj_id)
        self.mngr_id = mngr_doc['_id']
        self.mngr_token = token['token']

        with self.app.app_context():
            project_gid = get_admin_group_id(self.proj_id)

        self.user = self.create_user(roles={'subscriber'},
                                     groups=[project_gid, mngr_doc['owner']],
                                     token='user-token')

        # Create three test jobs, one of which is completed and two are queued.
        with self.app.test_request_context():
            force_cli_user()
            job = self.jmngr.api_create_job(
                'test job 1',
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
            self.jobid1 = job['_id']
            job = self.jmngr.api_create_job(
                'test job 2',
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
            self.jobid2 = job['_id']
            job = self.jmngr.api_create_job(
                'test job 3',
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
            self.jobid3 = job['_id']
            job = self.jmngr.api_create_job(
                'test job 4',
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
                start_paused=True,
            )
            self.jobid4 = job['_id']
            assert isinstance(self.jobid1, ObjectId)
            assert isinstance(self.jobid2, ObjectId)
            assert isinstance(self.jobid3, ObjectId)
            assert isinstance(self.jobid4, ObjectId)

            self.set_job_status('completed', job_id=self.jobid3)

            self.tasks = list(self.flamenco.db('tasks').find({
                'job': {'$in': [self.jobid1, self.jobid2]}
            }))
            self.task_ids = [t['_id'] for t in self.tasks]

    def test_get_clean_slate(self):
        from dateutil.parser import parse

        # Just so we have a task that's known to be last-updated.
        self.force_task_status(0, 'claimed-by-manager')

        resp = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                        auth_token=self.mngr_token)
        depsgraph = resp.json['depsgraph']
        self.assertEqual(len(self.tasks), len(depsgraph))
        self.assertEqual({str(t['_id']) for t in self.tasks},
                         {t['_id'] for t in depsgraph})

        # Tasks should be returned in full, no projection.
        task1 = self.tasks[1]
        depstask1 = next(t for t in depsgraph if t['_id'] == str(task1['_id']))
        self.assertEqual(set(task1.keys()), set(depstask1.keys()))

        # The 'X-Flamenco-Last-Updated' header should contain the last-changed task.
        last_modified = parse(resp.headers['X-Flamenco-Last-Updated'])
        with self.app.test_request_context():
            task0 = self.flamenco.db('tasks').find_one({'_id': self.task_ids[0]})
        self.assertEqual(task0['_updated'], last_modified)

        # The tasks in the database, as well as the response, should be set to claimed-by-manager
        with self.app.test_request_context():
            dbtasks = self.flamenco.db('tasks').find({'_id': {'$in': self.task_ids}})
            self.assertEqual(8 * ['claimed-by-manager'], [task['status'] for task in dbtasks])
        self.assertEqual(8 * ['claimed-by-manager'], [task['status'] for task in depsgraph])

    def test_get_clean_slate_some_tasks_unrunnable(self):
        self.force_task_status(0, 'failed')
        self.force_task_status(1, 'canceled')
        self.force_task_status(2, 'completed')

        resp = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                        auth_token=self.mngr_token)
        depsgraph = resp.json['depsgraph']
        self.assertEqual(len(self.tasks) - 3, len(depsgraph))

        deps_tids = {t['_id'] for t in depsgraph}
        self.assertEqual({str(tid) for tid in self.task_ids[3:]}, deps_tids)

        # The previously queued tasks in the database, as well as the response,
        # should be set to claimed-by-manager
        with self.app.test_request_context():
            dbtasks = self.flamenco.db('tasks').find({'_id': {'$in': self.task_ids}})
            self.assertEqual(['failed', 'canceled', 'completed'] + 5 * ['claimed-by-manager'],
                             [task['status'] for task in dbtasks])
        self.assertEqual(5 * ['claimed-by-manager'],
                         [task['status'] for task in depsgraph])

    def test_get_subsequent_call(self):
        import time
        from dateutil.parser import parse

        # Get a clean slate first, so that we get the timestamp of last modification
        log.info('Getting clean slate first, for timestamp')
        resp = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                        auth_token=self.mngr_token)
        last_modified = resp.headers['X-Flamenco-Last-Updated']

        # Do the subsequent call, it should return nothing.
        log.info('Getting changes since %s', last_modified)
        self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                 auth_token=self.mngr_token,
                 headers={'X-Flamenco-If-Updated-Since': last_modified},
                 expected_status=304)
        log.info('New last-modified is %s', resp.headers['X-Flamenco-Last-Updated'])

        # Change some tasks to see what we get back.
        time.sleep(0.05)  # sleep a bit to stabilise the test.
        self.force_task_status(0, 'claimed-by-manager')
        self.force_task_status(1, 'cancel-requested')
        self.force_task_status(2, 'queued')

        resp = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                        auth_token=self.mngr_token,
                        headers={'X-Flamenco-If-Updated-Since': last_modified})

        depsgraph = resp.json['depsgraph']
        self.assertEqual(2, len(depsgraph))  # we should not get the cancel-requested task back.

        deps_tids = {t['_id'] for t in depsgraph}
        self.assertEqual({str(self.task_ids[0]),
                          str(self.task_ids[2])},
                         deps_tids)

        # The 'X-Flamenco-Last-Updated' header should contain the last-changed task.
        last_modified = parse(resp.headers['X-Flamenco-Last-Updated'])
        with self.app.test_request_context():
            task0 = self.flamenco.db('tasks').find_one({'_id': self.task_ids[0]})
            task2 = self.flamenco.db('tasks').find_one({'_id': self.task_ids[2]})
        # They should be equal to second precision
        self.assertEqual(task2['_updated'], last_modified)

        self.assertEqual(task0['status'], 'claimed-by-manager')
        self.assertEqual(task2['status'], 'claimed-by-manager')
        self.assertEqual(2 * ['claimed-by-manager'],
                         [task['status'] for task in depsgraph])

    def test_changed_job_priority(self):
        # Get a clean slate first, so that we get the timestamp of last modification
        log.info('Getting clean slate first, for timestamp')
        resp = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                        auth_token=self.mngr_token)
        last_modified = resp.headers['X-Flamenco-Last-Updated']

        # Increase the priority of job 2 by PATCHing the job.
        self.patch(f'/api/flamenco/jobs/{self.jobid2}',
                   json={'op': 'set-job-priority', 'priority': 60},
                   expected_status=204,
                   auth_token='user-token')

        # Get the depsgraph again, we should get all the tasks of the changed job.
        resp = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                        auth_token=self.mngr_token,
                        headers={'X-Flamenco-If-Updated-Since': last_modified})
        last_modified = resp.headers['X-Flamenco-Last-Updated']

        depsgraph = resp.json['depsgraph']
        self.assertEqual(4, len(depsgraph))
        self.assertEqual(4 * [60], [task['job_priority'] for task in depsgraph])

        # Do the PATCH again but keep the same priority
        self.patch(f'/api/flamenco/jobs/{self.jobid2}',
                   json={'op': 'set-job-priority', 'priority': 60},
                   expected_status=204,
                   auth_token='user-token')

        # The depsgraph should be empty as nothing should have changed.
        self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                 auth_token=self.mngr_token,
                 headers={'X-Flamenco-If-Updated-Since': last_modified},
                 expected_status=304)
