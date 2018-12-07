# -*- encoding: utf-8 -*-

from bson import ObjectId

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class TaskPatchingTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user

        self.mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = self.mngr_doc['_id']
        self.mngr_token = token['token']

        uid = self.create_user(user_id=24 * 'f', roles={'flamenco-admin'})
        self.create_valid_auth_token(uid, 'fladmin-token')

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

    def test_set_task_invalid_status(self):
        chunk = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json['depsgraph']
        task = chunk[0]
        task_url = '/api/flamenco/tasks/%s' % task['_id']

        self.patch(
            task_url,
            json={'op': 'set-task-status',
                  'status': 'finished',
                  },
            auth_token='fladmin-token',
            expected_status=422,
        )

        # Check that the status in the database didn't change.
        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            task = tasks_coll.find_one({'_id': ObjectId(task['_id'])})
            self.assertEqual('claimed-by-manager', task['status'])

    def test_set_task_valid_status(self):
        chunk = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json['depsgraph']
        task = chunk[0]
        task_url = '/api/flamenco/tasks/%s' % task['_id']

        self.patch(
            task_url,
            json={'op': 'set-task-status',
                  'status': 'completed',
                  },
            auth_token='fladmin-token',
            expected_status=204,
        )

        # Check that the status in the database changed too.
        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            task = tasks_coll.find_one({'_id': ObjectId(task['_id'])})
            self.assertEqual('completed', task['status'])

    def test_job_status_change_due_to_task_patch(self):
        """A job should be marked as completed after all tasks are completed."""

        self.assert_job_status('queued')

        # The test job consists of 4 tasks; get their IDs through the scheduler.
        # This should set the job status to active.
        tasks = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json['depsgraph']
        self.assertEqual(4, len(tasks))

        # After setting tasks 1-3 to 'completed' the job should still not be completed.
        for task in tasks[:-1]:
            self.patch(
                '/api/flamenco/tasks/%s' % task['_id'],
                json={'op': 'set-task-status', 'status': 'completed'},
                auth_token='fladmin-token',
                expected_status=204,
            )
        self.assert_job_status('active')

        self.patch(
            '/api/flamenco/tasks/%s' % tasks[-1]['_id'],
            json={'op': 'set-task-status', 'status': 'completed'},
            auth_token='fladmin-token',
            expected_status=204,
        )
        self.assert_job_status('completed')

        # Re-queueing a task on a completed job should re-queue the job too.
        self.patch(
            '/api/flamenco/tasks/%s' % tasks[-1]['_id'],
            json={'op': 'set-task-status', 'status': 'queued'},
            auth_token='fladmin-token',
            expected_status=204,
        )
        self.assert_job_status('queued')

    def test_requeue_task_of_completed_job(self):
        """Re-queueing a single task of a completed job should keep the other tasks completed."""

        with self.app.app_context():
            tasks_coll = self.app.db('flamenco_tasks')
            tasks_coll.update_many({}, {'$set': {'status': 'completed'}})
            tasks = list(tasks_coll.find({'job': self.job_id}))
            one_task_id = tasks[-1]['_id']

        self.force_job_status('completed')

        # Re-queueing a task on a completed job should re-queue the job too,
        # but leave the completed tasks completed.
        self.patch(
            '/api/flamenco/tasks/%s' % one_task_id,
            json={'op': 'set-task-status', 'status': 'queued'},
            auth_token='fladmin-token',
            expected_status=204,
        )
        self.assert_job_status('queued')

        with self.app.app_context():
            for task in tasks_coll.find({'job': self.job_id}):
                if task['_id'] == one_task_id:
                    expected_status = 'queued'
                else:
                    expected_status = 'completed'
                self.assertEqual(expected_status, task['status'], f"for task {task['_id']}")

    def _get_first_task_id(self) -> str:
        """Uses the manager's token to get the first task ID from the depsgraph."""

        chunk = self.get('/api/flamenco/managers/%s/depsgraph' % self.mngr_id,
                         auth_token=self.mngr_token).json['depsgraph']
        task = chunk[0]
        task_id = task['_id']
        return task_id

    def test_outside_flamuser_permissions(self):
        """Check that a flamenco-user outside the project cannot PATCH."""

        self.create_user(user_id=24 * 'e',
                         roles={'subscriber'},
                         token='flamuser-token')

        task_id = self._get_first_task_id()
        self.patch(
            '/api/flamenco/tasks/%s' % task_id,
            json={'op': 'set-task-status',
                  'status': 'completed'},
            auth_token='flamuser-token',
            expected_status=403,
        )

        # Check that the status in the database didn't change too.
        self.assert_task_status(task_id, 'claimed-by-manager')

    def test_projmember_flamuser_permissions(self):
        """Check that a project member flamenco-user can PATCH a task to requeue it."""

        self.create_project_member(user_id=24 * 'e',
                                   roles={'subscriber'},
                                   token='flamuser-token')

        self.create_project_member(user_id=24 * 'd',
                                   roles={'subscriber'},
                                   groups=[self.mngr_doc['owner']],
                                   token='owner-token')

        task_id = self._get_first_task_id()
        self.force_task_status(task_id, 'failed')

        # Test without assigning the manager to the project
        self.patch(
            '/api/flamenco/tasks/%s' % task_id,
            json={'op': 'set-task-status',
                  'status': 'queued'},
            auth_token='flamuser-token',
            expected_status=403,
        )
        self.assert_task_status(task_id, 'failed')

        # Assign the manager to the project
        self.patch(
            f'/api/flamenco/managers/{self.mngr_id}',
            json={'op': 'assign-to-project',
                  'project': self.proj_id},
            auth_token='owner-token',
            expected_status=204,
        )

        # Test after assigning the manager to the project
        self.patch(
            '/api/flamenco/tasks/%s' % task_id,
            json={'op': 'set-task-status',
                  'status': 'queued'},
            auth_token='flamuser-token',
            expected_status=204,
        )
        self.assert_task_status(task_id, 'queued')


class ComplexerJobTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user

        self.mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = self.mngr_doc['_id']
        self.mngr_token = token['token']

        uid = self.create_user(user_id=24 * 'f', roles={'flamenco-admin'})
        self.create_valid_auth_token(uid, 'fladmin-token')

        with self.app.test_request_context():
            force_cli_user()
            job = self.jmngr.api_create_job(
                'test job',
                'Wörk wørk w°rk.',
                'blender-video-chunks',
                {
                    'frames': '100-250',
                    'fps': 24,
                    'chunk_size': 100,
                    'render_output': '/tmp/render/spring/export/FILENAME.MKV',
                    'filepath': '/spring/edit/sprloing.blend',
                    'output_file_extension': '.mkv',
                    'images_or_video': 'video',
                    'extract_audio': True,
                },
                self.proj_id,
                ctd.EXAMPLE_PROJECT_OWNER_ID,
                self.mngr_id,
            )
            self.job_id = job['_id']

    def test_requeue_task_and_successors(self):
        with self.app.app_context():
            tasks_coll = self.app.db('flamenco_tasks')
            tasks_coll.update_many({}, {'$set': {'status': 'completed'}})
            self.force_job_status('completed')

            one_task = tasks_coll.find_one({'name': 'frame-chunk-200-250', 'job': self.job_id})
            one_task_id = one_task['_id']

        # Re-queueing a task on a completed job should re-queue the job too,
        # and re-queue the successors.
        self.patch(
            '/api/flamenco/tasks/%s' % one_task_id,
            json={'op': 'requeue'},
            auth_token='fladmin-token',
            expected_status=204,
        )
        self.assert_job_status('queued')

        expected_requeue = {
            'frame-chunk-200-250',
            'video-chunk-200-250',
            'concatenate-videos',
            'mux-audio-video',
            'move-with-counter',
        }

        with self.app.app_context():
            for task in tasks_coll.find({'job': self.job_id}):
                if task['name'] in expected_requeue:
                    expected_status = 'queued'
                else:
                    expected_status = 'completed'
                self.assertEqual(expected_status, task['status'], f"for task {task['name']}")
