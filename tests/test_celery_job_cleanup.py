import datetime

from bson import ObjectId, tz_util

from abstract_flamenco_test import AbstractFlamencoTest
from pillar.tests import common_test_data as ctd


class CleanupWaitingForFilesTest(AbstractFlamencoTest):
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
        self.job_id = ObjectId(resp.json['_id'])
        self.assert_job_status('waiting-for-files')

    def test_recent_job(self):
        # Cleaning up should not touch this job, since it's too new.
        with self.app.app_context():
            from flamenco.celery import job_cleanup
            job_cleanup.remove_waiting_for_files()
        self.assert_job_status('waiting-for-files')

    def test_old_but_not_waiting_for_files(self):
        # Making the job 'old' but in a different status should also prevent its cleanup.
        old_updated = datetime.datetime.utcnow() - datetime.timedelta(days=1, seconds=5)
        self.force_job_status('queued')
        self.set_job_updated(old_updated)

        with self.app.app_context():
            from flamenco.celery import job_cleanup
            job_cleanup.remove_waiting_for_files()
        self.assert_job_status('queued')

    def test_old_and_waiting_for_files(self):
        # Making the job 'old' and waiting-for-files should allow cleanup.
        self.force_job_status('waiting-for-files')
        old_updated = datetime.datetime.utcnow() - datetime.timedelta(days=1, seconds=5)
        self.set_job_updated(old_updated)

        with self.app.app_context():
            from flamenco.celery import job_cleanup
            job_cleanup.remove_waiting_for_files()

            jobs_coll = self.flamenco.db('jobs')
            job = jobs_coll.find_one(self.job_id)
            self.assertIsNone(job)
