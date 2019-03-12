import datetime
import unittest
from unittest import mock

from bson import ObjectId, tz_util

from abstract_flamenco_test import AbstractFlamencoTest
from pillar.tests import common_test_data as ctd


class JobDocForTesting(dict):
    """Dict that doesn't show the contents in its repr().

    Used to make failing mock calls less verbose.
    """

    def __init__(self, somedict: dict):
        super().__init__(somedict)

    def __repr__(self):
        return '<test-job-doc>'


class SleepSimpleTest(unittest.TestCase):
    @mock.patch('datetime.datetime')
    def test_job_compilation(self, mock_datetime):
        from flamenco.job_compilers import sleep

        job_doc = {
            '_id': ObjectId(24 * 'f'),
            'settings': {
                'frames': '1-30, 40-44',
                'chunk_size': 13,
                'time_in_seconds': 3,
            }
        }
        task_manager = mock.Mock()
        job_manager = mock.Mock()

        # Create a stable 'now' for testing.
        mock_now = datetime.datetime.now(tz=tz_util.utc)
        mock_datetime.now.side_effect = [mock_now]

        compiler = sleep.Sleep(task_manager=task_manager, job_manager=job_manager)
        compiler.compile(job_doc)

        self._expect_create_task_calls(task_manager, job_doc)

        # Both calls should be performed with the same 'now'.
        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'queued', now=mock_now)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'queued', now=mock_now)

    def _expect_create_task_calls(self, task_manager, job_doc):
        from flamenco.job_compilers import commands

        task_manager.api_create_task.assert_has_calls([
            mock.call(
                job_doc,
                [
                    commands.Echo(message='Preparing to sleep'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-1-13',
                status='under-construction',
                task_type='sleep',
            ),
            mock.call(
                job_doc,
                [
                    commands.Echo(message='Preparing to sleep'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-14-26',
                status='under-construction',
                task_type='sleep',
            ),
            mock.call(
                job_doc,
                [
                    commands.Echo(message='Preparing to sleep'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-27-30,40-44',
                status='under-construction',
                task_type='sleep',
            ),
        ])

    @mock.patch('datetime.datetime')
    def test_start_paused(self, mock_datetime):
        from flamenco.job_compilers import sleep

        job_doc = {
            '_id': ObjectId(24 * 'f'),
            'settings': {
                'frames': '1-30, 40-44',
                'chunk_size': 13,
                'time_in_seconds': 3,
            },
            'start_paused': True,
        }
        task_manager = mock.Mock()
        job_manager = mock.Mock()

        # Create a stable 'now' for testing.
        mock_now = datetime.datetime.now(tz=tz_util.utc)
        mock_datetime.now.side_effect = [mock_now]

        compiler = sleep.Sleep(task_manager=task_manager, job_manager=job_manager)
        compiler.compile(job_doc)

        self._expect_create_task_calls(task_manager, job_doc)

        # Both calls should be performed with the same 'now'.
        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'paused', now=mock_now)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'paused', now=mock_now)


class CreateDeferredTest(AbstractFlamencoTest):
    def setUp(self):
        super().setUp()

        self.create_standard_groups()

        # Create a timestamp before we start mocking datetime.datetime.
        self.created = datetime.datetime(2018, 7, 6, 11, 52, 33, tzinfo=tz_util.utc)

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']

        self.create_user(user_id=24 * 'e',
                         roles={'subscriber'},
                         groups=[mngr_doc['owner'], ctd.EXAMPLE_ADMIN_GROUP_ID],
                         token='owner-token')
        with self.app.app_context():
            self.mmngr.api_assign_to_project(self.mngr_id, self.proj_id, 'assign')

    def test_create_deferred(self):
        job_doc = {
            '_id': ObjectId(24 * 'f'),
            'settings': {
                'frames': '1-4',
                'chunk_size': 13,
                'render_output': '{render}/some/output/there-######.png',
            },
            'job_type': 'blender-render',
            'manager': str(self.mngr_id),
            'name': 'Zzžžž',
            'project': str(self.proj_id),
            'start_paused': True,
            'status': 'waiting-for-files',
            'user': 24 * 'e',
        }
        resp = self.post('/api/flamenco/jobs', json=job_doc, auth_token='owner-token',
                         expected_status=201)
        job_id = ObjectId(resp.json['_id'])

        job_url = f'/api/flamenco/jobs/{job_id}'
        json_job = self.get(job_url, auth_token='owner-token').json
        self.assertEqual('waiting-for-files', json_job['status'])

        # Check that there are no tasks created.
        with self.app.app_context():
            tasks_coll = self.flamenco.db('tasks')
            self.assertEqual([], list(tasks_coll.find({'job': job_id})))

        # PATCH the job to get the task creation going.
        self.patch(job_url,
                   json={'op': 'construct', 'settings': {'filepath': '{shaman}/job/file.blend'}},
                   auth_token='owner-token',
                   expected_status=204)

        json_job = self.get(job_url, auth_token='owner-token').json
        self.assertEqual('paused', json_job['status'])
        self.assertEqual('{shaman}/job/file.blend', json_job['settings']['filepath'])

        with self.app.app_context():
            tasks = list(tasks_coll.find({'job': job_id}))

        self.assertEqual(2, len(tasks))
        self.assertEqual('{shaman}/job/file.blend', tasks[0]['commands'][0]['settings']['filepath'])
        for task in tasks:
            self.assertEqual(job_id, task['job'])
            self.assertEqual('paused', task['status'])
            self.assertEqual(self.mngr_id, task['manager'])


class CommandTest(unittest.TestCase):
    def test_to_dict(self):
        from flamenco.job_compilers import commands

        cmd = commands.Echo(message='Preparing to sleep')
        self.assertEqual({
            'name': 'echo',
            'settings': {
                'message': 'Preparing to sleep',
            }
        }, cmd.to_dict())
