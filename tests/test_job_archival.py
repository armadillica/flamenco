import datetime
import gzip
import json
import pathlib
import tempfile
from unittest import mock

import pillar.tests.common_test_data as ctd

from test_task_update_batch import AbstractTaskBatchUpdateTest

import bson
import bson.tz_util


class JobArchivalTest(AbstractTaskBatchUpdateTest):
    TASK_COUNT = 4

    def setUp(self, **kwargs):
        super().setUp(**kwargs)

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

        self.task_ids = [t['_id'] for t in self.do_schedule_tasks()]
        self.enter_app_context()

    def test_compress_flamenco_task_log(self):
        from pillar.api.utils import dumps
        from flamenco.celery import job_archival

        # Make sure there are log entries.
        for batch_idx in range(3):
            now = datetime.datetime.now(tz=bson.tz_util.utc)
            update_batch = [
                {'_id': str(bson.ObjectId()),
                 'task_id': task_id,
                 'activity': f'testing logging batch {batch_idx}',
                 'log': 40 * f'This is batch {batch_idx} mülti→line log entry\n',
                 'received_on_manager': now}
                for task_id in self.task_ids
            ]
            self.post(f'/api/flamenco/managers/{self.mngr_id}/task-update-batch',
                      json=update_batch,
                      auth_token=self.mngr_token)

        expected_log = ''.join(
            40 * f'This is batch {batch_idx} mülti→line log entry\n'
            for batch_idx in range(3))

        task_id = self.task_ids[1]
        test_task = self.flamenco.db('tasks').find_one({'_id': bson.ObjectId(task_id)})

        with tempfile.TemporaryDirectory() as tempdir:
            # Perform the task log compression
            storage_path = pathlib.Path(tempdir)
            job_archival.download_task_and_log(tempdir, task_id)

            # Check that the files are there and contain the correct data.
            task_log_file = storage_path / f'task-{task_id}.log.gz'
            with gzip.open(task_log_file) as infile:
                contents = infile.read().decode()
                self.assertEqual(expected_log, contents)

            task_contents_file = storage_path / f'task-{task_id}.json'
            expected_task = json.loads(dumps(test_task))

            with task_contents_file.open() as infile:
                read_task = json.load(infile)
                self.assertEqual(set(expected_task.keys()), set(read_task.keys()))
                self.assertEqual(expected_task, read_task)

    @mock.patch('celery.group')
    def test_write_job_as_json(self, mocked_group):
        import tempfile

        self.force_job_status('completed')
        jobs_coll = self.flamenco.db('jobs')
        job = jobs_coll.find_one(self.job_id)

        # Make sure we can predict where the JSON file will be written to.
        tempdir = tempfile.mkdtemp(prefix='unittests-')
        with mock.patch('tempfile.mkdtemp') as mock_mkdtemp:
            mock_mkdtemp.return_value = tempdir
            self.jmngr.archive_job(job)

        mocked_group.assert_called()

        json_path = pathlib.Path(tempdir) / f'job-{self.job_id}.json'
        self.assertTrue(json_path.exists())

        # Job status in JSON should be 'completed'.
        with json_path.open() as infile:
            json_job = json.load(infile)
        self.assertEqual('completed', json_job['status'])
        self.assertNotIn('pre_archive_status', json_job)

        # …but in the database should be 'archiving'.
        db_job = jobs_coll.find_one(self.job_id)
        self.assertEqual('archiving', db_job['status'])
        self.assertEqual('completed', db_job['pre_archive_status'])
