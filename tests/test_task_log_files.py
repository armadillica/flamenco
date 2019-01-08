import gzip
import io

from bson import ObjectId

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class TaskLogTest(AbstractFlamencoTest):
    """Tests for task log file uploads from Flamenco Manager."""

    def setUp(self):
        super().setUp()

        mngr_doc, account, token = self.create_manager_service_account(
            assign_to_project_id=self.proj_id)
        self.mngr_id = mngr_doc['_id']
        self.mngr_doc = self.fetch_manager_from_db(self.mngr_id)
        self.mngr_token = token['token']

        assert self.mngr_doc['owner']
        self.owner_uid = ObjectId(24 * 'e')
        self.create_project_member(user_id=str(self.owner_uid),
                                   roles={'subscriber'},
                                   groups=[self.mngr_doc['owner']],
                                   token='owner-token')

        from pillar.api.utils.authentication import force_cli_user

        with self.app.app_context():
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
            self.tasks = list(self.tmngr.collection().find({'job': self.job_id}))
            self.task = self.tasks[0]
            self.tid = self.task['_id']

            # Make sure we can request the task logs.
            self.tmngr.api_set_task_status_for_job(self.job_id, 'queued', 'completed')

    def test_request_task_log(self):
        self.patch(f'/api/flamenco/tasks/{self.tid}', json={'op': 'request-task-log-file'},
                   auth_token='owner-token', expected_status=204)

        # Check the database.
        with self.app.app_context():
            manager = self.mmngr.collection().find_one({'_id': self.mngr_id})
        self.assertEqual([{'job': self.job_id, 'task': self.tid}],
                         manager['upload_task_file_queue'])

        # Check the endpoint the Manager will queue.
        task_update_batch = self.url_for('flamenco.managers.api.task_update_batch',
                                         manager_id=str(self.mngr_id))
        resp = self.post(task_update_batch, auth_token=self.mngr_token)
        self.assertEqual([{'job': str(self.job_id), 'task': str(self.tid)}],
                         resp.json['upload_task_file_queue'])

    def test_attach_task_log(self):
        gzipped, resp = self.attach_log()

        download_log_url = self.url_for('flamenco.tasks.perproject.download_task_log_file',
                                        project_url=self.project['url'],
                                        task_id=str(self.tid))
        self.assertEqual(download_log_url, resp.headers['Location'])

        pid = str(self.proj_id)
        jid = str(self.job_id)
        tid = str(self.tid)
        file_storage_url = f'https://localhost.local/api/storage/file/{pid[:2]}/{pid}/fl/' \
            f'flamenco-task-logs/job-{jid}/task-{tid}.log.gz'
        with self.login_as(self.owner_uid):
            resp = self.get(download_log_url, expected_status=307)
            self.assertEqual(file_storage_url, resp.headers['Location'])

        resp = self.get(file_storage_url)
        self.assertEqual(gzipped, resp.data)
        self.assertEqual('application/octet-stream', resp.headers['Content-Type'])

        # These will be set by GCS, but not by the local storage backend we use for testing:
        # self.assertEqual('application/gzip', resp.headers['Content-Type'])
        # self.assertEqual('gzip', resp.headers['Content-Encoding'])
        # self.assertEqual(f'filename="task-{tid}.log.gz"', resp.headers['Content-Disposition'])

    def attach_log(self):
        log_contents = 'hello there\nsecond line²'
        gzipped = gzip.compress(log_contents.encode('utf8'))
        url = self.url_for('flamenco.managers.api.attach_task_log',
                           manager_id=str(self.mngr_id), task_id=str(self.tid))
        resp = self.post(url,
                         files={'logfile': (io.BytesIO(gzipped), 'task-123.log.gz')},
                         auth_token=self.mngr_token,
                         expected_status=201)
        return gzipped, resp

    def test_dequeue_after_attaching(self):
        self.patch(f'/api/flamenco/tasks/{self.tid}', json={'op': 'request-task-log-file'},
                   auth_token='owner-token', expected_status=204)

        log_contents = 'hello there\nsecond line²'
        gzipped = gzip.compress(log_contents.encode('utf8'))

        url = self.url_for('flamenco.managers.api.attach_task_log',
                           manager_id=str(self.mngr_id), task_id=str(self.tid))
        self.post(url,
                  files={'logfile': (io.BytesIO(gzipped), 'task-123.log.gz')},
                  headers={'Content-Encoding': 'gzip'},
                  auth_token=self.mngr_token,
                  expected_status=201)

        # Now that a log file has been attached, it should be un-queued from the Manager.
        with self.app.app_context():
            manager = self.mmngr.collection().find_one({'_id': self.mngr_id})
        self.assertFalse(manager['upload_task_file_queue'])

    def test_unlink_after_reclaim(self):
        _, resp = self.attach_log()
        download_task_url = resp.headers['Location']

        # Log file should be attached to this task.
        with self.login_as(self.owner_uid):
            self.get(download_task_url, expected_status=307)

        # Re-queueing the task should not break the link to the file on storage.
        self.patch(
            f'/api/flamenco/tasks/{self.tid}',
            json={'op': 'set-task-status', 'status': 'queued'},
            auth_token='owner-token',
            expected_status=204,
        )
        with self.login_as(self.owner_uid):
            self.get(download_task_url, expected_status=307)

        # The manager re-claiming the task should, though.
        self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id, auth_token=self.mngr_token)
        with self.login_as(self.owner_uid):
            self.get(download_task_url, expected_status=404)
