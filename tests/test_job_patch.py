# -*- encoding: utf-8 -*-

import mock

import bson

from pillar.tests import common_test_data as ctd

from abstract_flamenco_test import AbstractFlamencoTest
import flamenco.job_compilers.commands
import flamenco.job_compilers.blender_render


class JobPatchingTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user
        from pillar.api.projects.utils import get_admin_group_id

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']
        self.mngr_token = token['token']

        self.assign_manager_to_project(self.mngr_id, self.proj_id)

        with self.app.test_request_context():
            group_id = get_admin_group_id(self.proj_id)

        self.create_user(user_id=24 * 'f', roles={'flamenco-admin'}, groups=[group_id])
        self.create_valid_auth_token(24 * 'f', 'fladmin-token')

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

    def test_set_job_invalid_status(self):
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'set-job-status',
                  'status': 'finished'},
            auth_token='fladmin-token',
            expected_status=422,
        )

        # Check that the status in the database didn't change.
        with self.app.test_request_context():
            jobs_coll = self.flamenco.db('jobs')
            job = jobs_coll.find_one({'_id': self.job_id})
            self.assertEqual('queued', job['status'])

    def test_set_job_valid_status(self):
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'set-job-status',
                  'status': 'completed'},
            auth_token='fladmin-token',
            expected_status=204,
        )

        # Check that the status in the database changed too.
        with self.app.test_request_context():
            jobs_coll = self.flamenco.db('jobs')
            job = jobs_coll.find_one({'_id': self.job_id})
            self.assertEqual('completed', job['status'])

    @mock.patch('flamenco.jobs.JobManager.handle_job_status_change')
    def test_task_status_change_due_to_job_patch(self, mock_handle_job_status_change):
        self.assert_job_status('queued')

        mock_handle_job_status_change.return_value = None
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'set-job-status',
                  'status': 'completed'},
            auth_token='fladmin-token',
            expected_status=204,
        )

        mock_handle_job_status_change.assert_called_with(
            self.job_id, 'queued', 'completed')
        self.assert_job_status('completed')

    @mock.patch('flamenco.jobs.JobManager.handle_job_status_change')
    def test_set_job_valid_status_as_outside_subscriber(self, mock_handle_job_status_change):
        """Flamenco users not member of the project should not be allowed to do this."""

        self.create_user(user_id=24 * 'e', roles={'subscriber'},
                         token='flamuser-token')

        self.assert_job_status('queued')
        mock_handle_job_status_change.return_value = None
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'set-job-status',
                  'status': 'completed'},
            auth_token='flamuser-token',
            expected_status=403,
        )

        mock_handle_job_status_change.assert_not_called()
        self.assert_job_status('queued')

    @mock.patch('flamenco.jobs.JobManager.handle_job_status_change')
    def test_set_job_valid_status_as_projmember_subscriber(self, mock_handle_job_status_change):
        """Subscribers member of the project should be allowed to do this."""

        from pillar.api.projects.utils import get_admin_group_id

        with self.app.test_request_context():
            admin_group_id = get_admin_group_id(self.proj_id)

        self.create_user(user_id=24 * 'e', roles={'subscriber'},
                         groups=[admin_group_id],
                         token='flamuser-token')

        self.assert_job_status('queued')
        mock_handle_job_status_change.return_value = None
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'set-job-status',
                  'status': 'completed'},
            auth_token='flamuser-token',
            expected_status=204,
        )

        mock_handle_job_status_change.assert_called_with(
            self.job_id, 'queued', 'completed')
        self.assert_job_status('completed')

    @mock.patch('flamenco.tasks.TaskManager.api_set_task_status_for_job')
    def test_requeue_failed_tasks(self, mock_api_set_task_status_for_job):
        self.force_job_status('active')

        mock_api_set_task_status_for_job.return_value = None
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'requeue-failed-tasks'},
            auth_token='fladmin-token',
            expected_status=204,
        )

        mock_api_set_task_status_for_job.assert_called_with(
            self.job_id, from_status='failed', to_status='queued')
        self.assert_job_status('active')


class AbstractRNAOverridesTest(AbstractFlamencoTest):

    def assertValidOverrideTask(self, override, override_task):
        self.assertEqual(flamenco.job_compilers.blender_render.RNA_OVERRIDES_TASK_NAME,
                         override_task['name'])

        self.assertEqual(1, len(override_task['commands']))
        cmd0 = override_task['commands'][0]
        self.assertEqual('create_python_file', cmd0['name'])

        contents = cmd0['settings']['contents']
        self.assertTrue(contents.endswith(f'{override}\n'),
                        f'{contents!r} should end with {override!r} + a newline')

        self.assertEqual('file-management', override_task['task_type'])
        self.assertEqual(80, override_task['priority'])


class RNAOverridesTest(AbstractRNAOverridesTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user
        from pillar.api.projects.utils import get_admin_group_id

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']
        self.mngr_token = token['token']

        self.assign_manager_to_project(self.mngr_id, self.proj_id)

        with self.app.test_request_context():
            group_id = get_admin_group_id(self.proj_id)

        self.create_user(user_id=24 * 'f', roles={'flamenco-admin'}, groups=[group_id])
        self.create_valid_auth_token(24 * 'f', 'fladmin-token')

        with self.app.test_request_context():
            force_cli_user()
            job = self.jmngr.api_create_job(
                'test job',
                'Wörk wørk w°rk.',
                'blender-render',
                {
                    'frames': '12-18',
                    'chunk_size': 5,
                    'render_output': '/render/out/frames-######',
                    'format': 'EXR',
                    'filepath': '/agent327/scenes/someshot/somefile.blend',
                    'blender_cmd': '/path/to/blender --enable-new-depsgraph',
                },
                self.proj_id,
                ctd.EXAMPLE_PROJECT_OWNER_ID,
                self.mngr_id,
            )
            self.job_id = job['_id']

    def test_rna_overrides_new(self) -> bson.ObjectId:
        override = 'bpy.context.scene.render.stamp_note_text = "je moeder"'

        self.force_job_status('active')
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'rna-overrides',
                  'rna_overrides': [
                      override,
                  ]},
            auth_token='fladmin-token',
            expected_status=204,
        )
        self.assert_job_status('active')

        # Check the parent pointers of the existing tasks.
        # This is a simple blender-render job, so all blender-render tasks
        # should point to the new task.
        with self.app.app_context():
            tasks_coll = self.flamenco.db('tasks')
            tasks = list(tasks_coll
                         .find({'job': self.job_id})
                         .sort([('priority', -1), ('_id', 1)]))
        # Expecting an override task, 2 render tasks, and a 'move to final' task.
        self.assertEqual(4, len(tasks))

        override_task = tasks[0]
        self.assertValidOverrideTask(override, override_task)

        self.assertEqual('queued', override_task['status'])
        self.assertNotIn('parents', override_task)
        self.assertEqual([override_task['_id']], tasks[1]['parents'])
        self.assertEqual([override_task['_id']], tasks[2]['parents'])
        self.assertEqual([tasks[1]['_id'], tasks[2]['_id']], tasks[3]['parents'])

        return override_task['_id']

    def test_rna_overrides_update(self):
        override_tid = self.test_rna_overrides_new()
        with self.app.app_context():
            tasks_coll = self.flamenco.db('tasks')
            orig_override_task = tasks_coll.find_one({'_id': override_tid})

        override = 'bpy.context.scene.render.use_stamp_note = False'

        self.force_job_status('active')
        self.force_task_status(override_tid, 'completed')

        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'rna-overrides',
                  'rna_overrides': [
                      override,
                  ]},
            auth_token='fladmin-token',
            expected_status=204,
        )
        self.assert_job_status('active')

        # Check the parent pointers of the existing tasks.
        # This is a simple blender-render job, so all blender-render tasks
        # should point to the new task.
        with self.app.app_context():
            tasks = list(tasks_coll
                         .find({'job': self.job_id})
                         .sort([('priority', -1), ('_id', 1)]))
        # Expecting the same override task, 2 render tasks, and a 'move to final' task.
        self.assertEqual(4, len(tasks))

        override_task = tasks[0]
        self.assertEqual(override_tid, override_task['_id'])

        self.assertValidOverrideTask(override, override_task)

        self.assertEqual('queued', override_task['status'])
        self.assertNotIn('parents', override_task)
        self.assertEqual([override_task['_id']], tasks[1]['parents'])
        self.assertEqual([override_task['_id']], tasks[2]['parents'])
        self.assertEqual([tasks[1]['_id'], tasks[2]['_id']], tasks[3]['parents'])

        self.assertNotEqual(orig_override_task['_etag'], override_task['_etag'])


class RNAOverridesTestProgressiveRender(AbstractRNAOverridesTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user
        from pillar.api.projects.utils import get_admin_group_id

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']
        self.mngr_token = token['token']

        self.assign_manager_to_project(self.mngr_id, self.proj_id)

        with self.app.test_request_context():
            group_id = get_admin_group_id(self.proj_id)

        self.create_user(user_id=24 * 'f', roles={'flamenco-admin'}, groups=[group_id])
        self.create_valid_auth_token(24 * 'f', 'fladmin-token')

        with self.app.test_request_context():
            force_cli_user()
            job = self.jmngr.api_create_job(
                'test job',
                'Wörk wørk w°rk.',
                'blender-render-progressive',
                {
                    'frames': '1-5',
                    'chunk_size': 2,
                    'render_output': '/render/out/frames-######',
                    'format': 'EXR',
                    'fps': 44,
                    'filepath': '/agent327/scenes/someshot/somefile.blend',
                    'blender_cmd': '/path/to/blender --enable-new-depsgraph',
                    'cycles_sample_count': 30,
                    'cycles_sample_cap': 30,
                },
                self.proj_id,
                ctd.EXAMPLE_PROJECT_OWNER_ID,
                self.mngr_id,
            )
            self.job_id = job['_id']

    def test_rna_overrides_new(self):
        override = 'bpy.context.scene.render.stamp_note_text = "je moeder"'

        # Make some lists of task IDs before we PATCH.
        with self.app.app_context():
            tasks_coll = self.flamenco.db('tasks')
            rm_tree_task = tasks_coll.find_one({'job': self.job_id,
                                                'name': 'destroy-preexisting-intermediate'})
            render_tasks = list(tasks_coll.find({'job': self.job_id,
                                                 'task_type': 'blender-render',
                                                 'parents': [rm_tree_task['_id']]}))
            task_count = tasks_coll.count({'job': self.job_id})

        # Just checking some assumptions this test relies on.
        for task in render_tasks:
            self.assertEqual([rm_tree_task['_id']], task['parents'])

        # Perform the PATCH
        self.force_job_status('active')
        self.patch(
            '/api/flamenco/jobs/%s' % self.job_id,
            json={'op': 'rna-overrides',
                  'rna_overrides': [
                      override,
                  ]},
            auth_token='fladmin-token',
            expected_status=204,
        )
        self.assert_job_status('active')

        # Check the parent pointers of the existing tasks.
        # This is a blender-render-progressive job, so all blender-render tasks
        # should point to the new task.
        with self.app.app_context():
            tasks_coll = self.flamenco.db('tasks')
            tasks = list(tasks_coll
                         .find({'job': self.job_id})
                         .sort([('_id', 1)]))
        self.assertEqual(task_count+1, len(tasks))

        override_task = tasks[-1]
        self.assertValidOverrideTask(override, override_task)

        with self.app.app_context():
            # Each render task should now have the RNA Override task as parent.
            for task in render_tasks:
                db_task = tasks_coll.find_one({'_id': task['_id']})
                self.assertEqual([override_task['_id']], db_task['parents'])
