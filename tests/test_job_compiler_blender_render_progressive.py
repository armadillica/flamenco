import datetime
import logging
import unittest
from unittest import mock

from bson import ObjectId, tz_util

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest
from test_job_compilers import JobDocForTesting


class BlenderRenderProgressiveTest(unittest.TestCase):
    def setUp(self):
        # Create a timestamp before we start mocking datetime.datetime.
        self.created = datetime.datetime(2018, 7, 6, 11, 52, 33, tzinfo=tz_util.utc)

    def test_chunk_generator(self):
        from flamenco.job_compilers import blender_render_progressive as brp
        cg = brp.ChunkGenerator(400, 100, uncapped_chunks=5)
        expected = [
            (1, 10),
            (11, 49),
            (50, 133),
            (134, 222),
            (223, 311),
            (312, 400),
        ]
        self.assertEqual(expected, list(cg))
        self.assertEqual(expected, list(cg), 're-iterating "cg" should work')

        cg = brp.ChunkGenerator(400, 100, uncapped_chunks=4)
        samples = [(end - start + 1) for start, end in cg]
        self.assertEqual([10, 62, 82, 82, 82, 82], samples)

        cg = brp.ChunkGenerator(30, 3000, uncapped_chunks=3)
        expected = [
            (1, 1),
            (2, 10),
            (11, 30),
        ]
        self.assertEqual(expected, list(cg))

    def test_dynamic_frame_chunking(self):
        from flamenco.job_compilers import blender_render_progressive as brp

        task_manager = mock.Mock()
        job_manager = mock.Mock()
        compiler = brp.BlenderRenderProgressive(
            task_manager=task_manager, job_manager=job_manager)

        # 100 samples / 10 samples per frame = 10 frames.
        self.assertEqual(10, compiler._frame_chunk_size(
            max_samples_per_task=100,
            total_frame_count=30,
            current_sample_count=10,
        ))

        # 100 samples / 40 samples per frame = 2.5 frames, so should be 2 per task
        self.assertEqual(2, compiler._frame_chunk_size(
            max_samples_per_task=100,
            total_frame_count=30,
            current_sample_count=40,
        ))

        # 100 samples / 20 samples per frame = 5 frames, but this would give 2 tasks
        # with 5 resp. 2 frame each. A chunk size of 4 would result in more even spread.
        self.assertEqual(4, compiler._frame_chunk_size(
            max_samples_per_task=100,
            total_frame_count=7,
            current_sample_count=20,
        ))

        # 100 samples / 10 samples per frame = 10 frames per task, but this would give
        # tasks [10, 10, ..., 1]. A chunk size of 9 would result in more even spread.
        self.assertEqual(9, compiler._frame_chunk_size(
            max_samples_per_task=100,
            total_frame_count=301,
            current_sample_count=10,
        ))

    def test_nonexr_job(self):
        from flamenco.job_compilers import blender_render_progressive
        from flamenco.exceptions import JobSettingError

        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            '_created': self.created,
            'settings': {
                'frames': '1-6',
                'chunk_size': 2,
                'render_output': '/render/out/frames-######',
                'format': 'JPEG',
                'fps': 3.4,
                'filepath': '/agent327/scenes/someshot/somefile.blend',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',
                'cycles_sample_count': 30,
                'cycles_sample_cap': 5,
            },
            'job_type': 'blender-render-progressive',
        })
        task_manager = mock.Mock()
        job_manager = mock.Mock()
        compiler = blender_render_progressive.BlenderRenderProgressive(
            task_manager=task_manager, job_manager=job_manager)

        try:
            compiler.compile(job_doc)
        except JobSettingError as ex:
            self.assertIn('EXR', str(ex))
        else:
            self.fail('expected exception JobSettingError not raised')

    def test_old_style_job(self):
        from flamenco.job_compilers import blender_render_progressive
        from flamenco.exceptions import JobSettingError

        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            '_created': self.created,
            'settings': {
                'frames': '1-6',
                'chunk_size': 2,
                'render_output': '/render/out/frames-######',
                'format': 'JPEG',
                'filepath': '/agent327/scenes/someshot/somefile.blend',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',
                'cycles_sample_count': 30,
                'cycles_num_chunks': 3,
            },
            'job_type': 'blender-render-progressive',
        })
        task_manager = mock.Mock()
        job_manager = mock.Mock()
        compiler = blender_render_progressive.BlenderRenderProgressive(
            task_manager=task_manager, job_manager=job_manager)

        try:
            compiler.compile(job_doc)
        except JobSettingError as ex:
            self.assertIn('Blender Cloud add-on', str(ex))
        else:
            self.fail('expected exception JobSettingError not raised')

    @mock.patch('datetime.datetime')
    def test_small_job(self, mock_datetime):
        from flamenco.job_compilers import blender_render_progressive, commands

        logging.basicConfig(level=logging.DEBUG)

        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            '_created': self.created,
            'settings': {
                'frames': '1-5',
                'chunk_size': 3,
                'render_output': '/render/out/frames-######',
                'fps': 5.3,
                'format': 'OPEN_EXR',
                'filepath': '/agent327/scenes/someshot/somefile.blend',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',
                'cycles_sample_count': 30,

                # Effectively uncapped so that the number of tasks stays small.
                # The actual capping is tested in test_chunk_generator() anyway.
                'cycles_sample_cap': 30,
            },
            'job_type': 'blender-render-progressive',
        })
        task_manager = mock.Mock()
        job_manager = mock.Mock()

        # Create a stable 'now' for testing.
        mock_now = datetime.datetime.now(tz=tz_util.utc)
        mock_datetime.now.side_effect = [mock_now]

        task_ids = [ObjectId() for _ in range(17)]
        task_manager.api_create_task.side_effect = task_ids

        compiler = blender_render_progressive.BlenderRenderProgressive(
            task_manager=task_manager, job_manager=job_manager)
        compiler._uncapped_chunk_count = 3  # Reduce to a testable number of tasks.
        compiler.compile(job_doc)

        task_manager.api_create_task.assert_has_calls([
            # Pre-existing intermediate directory is destroyed.
            mock.call(  # task 0
                job_doc,
                [commands.RemoveTree(path='/render/out__intermediate-2018-07-06_115233')],
                'destroy-preexisting-intermediate',
                status='under-construction',
                task_type='file-management',
            ),

            # First Cycles chunk goes into intermediate directory
            mock.call(  # task 1
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='OPEN_EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/render-smpl-0001-0001-######',
                    frames='1..5',
                    cycles_num_chunks=30,
                    cycles_chunk_start=1,
                    cycles_chunk_end=1)],
                'render-s_1-1-f_1-5',
                priority=0,
                parents=[task_ids[0]],
                status='under-construction',
                task_type='blender-render',
            ),

            mock.call(  # task 2
                job_doc,
                [commands.ExrSequenceToJpeg(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    exr_glob='/render/out__intermediate-2018-07-06_115233/render-smpl-0001-0001-*.exr',
                    output_pattern='preview-######',
                )],
                'create-preview-images',
                priority=1,
                parents=[task_ids[1]],
                status='under-construction',
                task_type='blender-render',
            ),
            mock.call(  # task 3
                job_doc,
                [commands.CreateVideo(
                    input_files='/render/out__intermediate-2018-07-06_115233/preview-*.jpg',
                    output_file='/render/out__intermediate-2018-07-06_115233/preview.mkv',
                    fps=5.3,
                )],
                'create-preview-video',
                priority=1,
                parents=[task_ids[2]],
                status='under-construction',
                task_type='video-encoding',
            ),

            # Second Cycles chunk renders to intermediate directory.
            mock.call(  # task 4
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='OPEN_EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/render-smpl-0002-0010-######',
                    frames='1..5',
                    cycles_num_chunks=30,
                    cycles_chunk_start=2,
                    cycles_chunk_end=10)],
                'render-s_2-10-f_1-5',
                priority=-10,
                parents=[task_ids[0]],
                status='under-construction',
                task_type='blender-render',
            ),

            # First merge pass, outputs to intermediate directory and copies to output dir
            mock.call(  # task 5
                job_doc,
                [
                    commands.MergeProgressiveRenderSequence(
                        blender_cmd='/path/to/blender --enable-new-depsgraph',
                        input1='/render/out__intermediate-2018-07-06_115233/render-smpl-0001-0001-000001.exr',
                        input2='/render/out__intermediate-2018-07-06_115233/render-smpl-0002-0010-000001.exr',
                        output='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-######',
                        weight1=1,
                        weight2=9,
                        frame_start=1,
                        frame_end=5,
                    ),
                ],
                'merge-to-s_10-f_1-5',
                parents=[task_ids[1], task_ids[4]],
                priority=1,
                status='under-construction',
                task_type='exr-merge',
            ),
            mock.call(  # task 6
                job_doc,
                [commands.ExrSequenceToJpeg(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    exr_glob='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-*.exr',
                    output_pattern='preview-######',
                )],
                'create-preview-images',
                priority=1,
                parents=[task_ids[2], task_ids[5]],
                status='under-construction',
                task_type='blender-render',
            ),
            mock.call(  # task 7
                job_doc,
                [commands.CreateVideo(
                    input_files='/render/out__intermediate-2018-07-06_115233/preview-*.jpg',
                    output_file='/render/out__intermediate-2018-07-06_115233/preview.mkv',
                    fps=5.3,
                )],
                'create-preview-video',
                priority=1,
                parents=[task_ids[3], task_ids[6]],
                status='under-construction',
                task_type='video-encoding',
            ),

            # Third Cycles chunk renders to intermediate directory.
            mock.call(  # task 8
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='OPEN_EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/render-smpl-0011-0030-######',
                    frames='1..3',
                    cycles_num_chunks=30,
                    cycles_chunk_start=11,
                    cycles_chunk_end=30)],
                'render-s_11-30-f_1-3',
                priority=-20,
                parents=[task_ids[0]],
                status='under-construction',
                task_type='blender-render',
            ),
            mock.call(  # task 9
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='OPEN_EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/render-smpl-0011-0030-######',
                    frames='4,5',
                    cycles_num_chunks=30,
                    cycles_chunk_start=11,
                    cycles_chunk_end=30)],
                'render-s_11-30-f_4,5',
                priority=-20,
                parents=[task_ids[0]],
                status='under-construction',
                task_type='blender-render',
            ),

            # Final merge pass. Could happen directly to the output directory, but to ensure the
            # intermediate directory shows a complete picture (pun intended), we take a similar
            # approach as earlier merge passes.
            mock.call(  # task 10
                job_doc,
                [
                    commands.MergeProgressiveRenderSequence(
                        blender_cmd='/path/to/blender --enable-new-depsgraph',
                        input1='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-000001.exr',
                        input2='/render/out__intermediate-2018-07-06_115233/render-smpl-0011-0030-000001.exr',
                        output='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-######',
                        weight1=10,
                        weight2=20,
                        frame_start=1,
                        frame_end=5,
                    ),
                ],
                'merge-to-s_30-f_1-5',
                parents=[task_ids[5], task_ids[8], task_ids[9]],
                priority=1,
                status='under-construction',
                task_type='exr-merge',
            ),

            mock.call(  # task 11
                job_doc,
                [commands.ExrSequenceToJpeg(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    exr_glob='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-*.exr',
                    output_pattern='preview-######',
                )],
                'create-preview-images',
                priority=1,
                parents=[task_ids[6], task_ids[10]],
                status='under-construction',
                task_type='blender-render',
            ),
            mock.call(  # task 12
                job_doc,
                [commands.CreateVideo(
                    input_files='/render/out__intermediate-2018-07-06_115233/preview-*.jpg',
                    output_file='/render/out__intermediate-2018-07-06_115233/preview.mkv',
                    fps=5.3,
                )],
                'create-preview-video',
                priority=1,
                parents=[task_ids[7], task_ids[11]],
                status='under-construction',
                task_type='video-encoding',
            ),

            mock.call(  # task 13
                job_doc,
                [
                    commands.MoveOutOfWay(src='/render/out'),
                ],
                'move-outdir-out-of-way',
                priority=1,
                parents=[task_ids[10]],
                status='under-construction',
                task_type='file-management',
            ),

            mock.call(  # task 14
                job_doc,
                [
                    commands.CopyFile(
                        src='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-000001.exr',
                        dest='/render/out/frames-000001.exr',
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-000002.exr',
                        dest='/render/out/frames-000002.exr',
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-000003.exr',
                        dest='/render/out/frames-000003.exr',
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-000004.exr',
                        dest='/render/out/frames-000004.exr',
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-000005.exr',
                        dest='/render/out/frames-000005.exr',
                    ),
                ],
                'publish-exr-to-output',
                priority=1,
                parents=[task_ids[13]],
                status='under-construction',
                task_type='file-management',
            ),
            mock.call(  # task 15
                job_doc,
                [
                    commands.CopyFile(
                        src='/render/out__intermediate-2018-07-06_115233/preview-000001.jpg',
                        dest='/render/out/frames-000001.jpg',
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate-2018-07-06_115233/preview-000002.jpg',
                        dest='/render/out/frames-000002.jpg',
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate-2018-07-06_115233/preview-000003.jpg',
                        dest='/render/out/frames-000003.jpg',
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate-2018-07-06_115233/preview-000004.jpg',
                        dest='/render/out/frames-000004.jpg',
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate-2018-07-06_115233/preview-000005.jpg',
                        dest='/render/out/frames-000005.jpg',
                    ),
                ],
                'publish-jpeg-to-output',
                priority=1,
                parents=[task_ids[11], task_ids[13]],
                status='under-construction',
                task_type='file-management',
            ),
            mock.call(  # task 16
                job_doc,
                [
                    commands.CopyFile(
                        src='/render/out__intermediate-2018-07-06_115233/preview.mkv',
                        dest='/render/out/preview.mkv',
                    ),
                ],
                'publish-video-to-output',
                priority=1,
                parents=[task_ids[12], task_ids[13]],
                status='under-construction',
                task_type='file-management',
            ),
        ])

        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'queued', now=mock_now)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'queued', now=mock_now)


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
                'frames': '1-5',
                'chunk_size': 3,
                'render_output': '/render/out/frames-######',
                'fps': 5.3,
                'format': 'OPEN_EXR',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',
                'cycles_sample_count': 30,

                # Effectively uncapped so that the number of tasks stays small.
                # The actual capping is tested in test_chunk_generator() anyway.
                'cycles_sample_cap': 30,
            },
            'job_type': 'blender-render-progressive',
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
        filepath = '{shaman}/jo/b-id/scenes/someshot/somefile.blend'
        self.patch(job_url,
                   json={'op': 'construct', 'settings': {'filepath': filepath}},
                   auth_token='owner-token',
                   expected_status=204)

        json_job = self.get(job_url, auth_token='owner-token').json
        self.assertEqual('paused', json_job['status'])
        self.assertEqual(filepath, json_job['settings']['filepath'])

        with self.app.app_context():
            tasks = list(tasks_coll.find({'job': job_id}))

        self.assertEqual('{shaman}/jo/b-id/scenes/someshot/somefile.blend',
                         tasks[1]['commands'][0]['settings']['filepath'])
        for task in tasks:
            self.assertEqual(job_id, task['job'])
            self.assertEqual('paused', task['status'])
            self.assertEqual(self.mngr_id, task['manager'])
