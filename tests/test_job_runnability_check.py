from bson import ObjectId

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class JobRunnabilityTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']
        self.mngr_token = token['token']

    def create_job(self, job_type: str) -> ObjectId:
        from pillar.api.utils.authentication import force_cli_user

        with self.app.test_request_context():
            force_cli_user()
            job = self.jmngr.api_create_job(
                'test job',
                'Wörk wørk w°rk.',
                job_type,
                {
                    'frames': '1-5',
                    'chunk_size': 3,
                    'render_output': '/render/out/frames-######',
                    'fps': 5.3,
                    'format': 'OPEN_EXR',
                    'filepath': '/agent327/scenes/someshot/somefile.blend',
                    'blender_cmd': '/path/to/blender --enable-new-depsgraph',
                    'cycles_sample_count': 30,
                    # Effectively uncapped so that the number of tasks stays small.
                    'cycles_sample_cap': 30,
                },
                self.proj_id,
                ctd.EXAMPLE_PROJECT_OWNER_ID,
                self.mngr_id,
            )
        return job['_id']

    def test_progressive_render(self):
        self.job_id = self.create_job('blender-render-progressive')

        tasks = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json['depsgraph']

        # Just check/set some things we assume in this test.
        self.assertEqual('create-preview-images', tasks[2]['name'])
        self.assertEqual([tasks[1]['_id']], tasks[2]['parents'])
        self.force_job_status('active')

        self.enter_app_context()

        from flamenco.celery import job_runnability_check as jrc

        # At first everything is runnable.
        self.assertEqual([], jrc._nonrunnable_tasks(self.job_id))

        # When we soft0fail task 1, task 2 is still runnable.
        self.force_task_status(tasks[1]['_id'], 'soft-failed')
        self.assertEqual([], jrc._nonrunnable_tasks(self.job_id))
        jrc.runnability_check(str(self.job_id))
        self.assert_job_status('active')

        # When we fail task 1, task 2 becomes unrunnable, and this should fail the job.
        self.force_task_status(tasks[1]['_id'], 'failed')
        self.assertIn(ObjectId(tasks[2]['_id']), jrc._nonrunnable_tasks(self.job_id))

        # If the job isn't active, the runnability check shouldn't do anything.
        self.force_job_status('queued')
        jrc.runnability_check(str(self.job_id))
        self.assert_job_status('queued')

        # If the job is active, the check should fail the job.
        self.force_job_status('active')
        jrc.runnability_check(str(self.job_id))
        self.assert_job_status('fail-requested')

        job_doc = self.flamenco.db('jobs').find_one(self.job_id)
        self.assertIn('tasks have a failed/cancelled parent and will not be able to run.',
                      job_doc['status_reason'])

    def test_regular_render(self):
        self.job_id = self.create_job('blender-render')

        tasks = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json['depsgraph']

        # Just check/set some things we assume in this test.
        self.assertEqual('blender-render-1-3', tasks[0]['name'])
        self.assertEqual('blender-render-4,5', tasks[1]['name'])
        self.assertIn(tasks[0]['_id'], tasks[-1]['parents'])
        self.assertIn(tasks[1]['_id'], tasks[-1]['parents'])
        self.force_job_status('active')

        self.enter_app_context()

        from flamenco.celery import job_runnability_check as jrc

        # At first everything is runnable.
        self.assertEqual([], jrc._nonrunnable_tasks(self.job_id))

        # When we soft-fail task 0 and 1, task -1 is still runnable, and the job should stay active.
        self.force_task_status(tasks[0]['_id'], 'soft-failed')
        self.force_task_status(tasks[1]['_id'], 'soft-failed')

        self.assertEqual([], jrc._nonrunnable_tasks(self.job_id))
        jrc.runnability_check(str(self.job_id))
        self.assert_job_status('active')

        # When we fail task 0 and 1, task -1 becomes unrunnable, and this should fail the job.
        self.force_task_status(tasks[0]['_id'], 'failed')
        self.force_task_status(tasks[1]['_id'], 'failed')

        # The nonrunnable tasks shouldn't have any duplicates.
        self.assertEqual([ObjectId(tasks[-1]['_id'])], jrc._nonrunnable_tasks(self.job_id))

        jrc.runnability_check(str(self.job_id))
        self.assert_job_status('fail-requested')
