import datetime
import logging
import pathlib
import unittest
from unittest import mock

from bson import ObjectId, tz_util

from abstract_flamenco_test import AbstractFlamencoTest


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
        from flamenco.job_compilers import sleep, commands

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


class BlenderRenderTest(AbstractFlamencoTest):
    def setUp(self):
        super().setUp()

        # Create a timestamp before we start mocking datetime.datetime.
        self.created = datetime.datetime(2018, 7, 6, 11, 52, 33, tzinfo=tz_util.utc)

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']

    def test_intermediate_path(self):
        from flamenco.job_compilers import blender_render

        job_doc = JobDocForTesting({
            '_created': self.created,
        })

        render_path = pathlib.PurePosixPath('/path/to/output')
        path = blender_render.intermediate_path(job_doc, render_path)
        self.assertEqual(
            pathlib.PurePath('/path/to/output__intermediate-2018-07-06_115233'),
            path
        )

    @mock.patch('datetime.datetime')
    def test_small_job(self, mock_datetime):
        from flamenco.job_compilers import blender_render, commands

        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            '_created': self.created,
            'settings': {
                'frames': '1-5',
                'chunk_size': 2,
                'render_output': '/render/out/frames-######',
                'format': 'EXR',
                'filepath': '/agent327/scenes/someshot/somefile.blend',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',
            },
            'job_type': 'blender-render',
        })

        task_manager = mock.Mock()
        job_manager = mock.Mock()

        # Create a stable 'now' for testing.
        mock_now = datetime.datetime.now(tz=tz_util.utc)
        mock_datetime.now.side_effect = [mock_now]

        # We expect:
        # - 3 frame chunks of 2 frames each
        # - 1 move-to-final task
        # so that's 4 tasks in total.
        task_ids = [ObjectId() for _ in range(4)]
        task_manager.api_create_task.side_effect = task_ids

        compiler = blender_render.BlenderRender(
            task_manager=task_manager, job_manager=job_manager)
        compiler.compile(job_doc)

        task_manager.api_create_task.assert_has_calls([
            # Render tasks
            mock.call(
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/frames-######',
                    frames='1,2')],
                'blender-render-1,2',
                status='under-construction',
                task_type='blender-render',
                parents=None,
            ),
            mock.call(
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/frames-######',
                    frames='3,4')],
                'blender-render-3,4',
                status='under-construction',
                task_type='blender-render',
                parents=None,
            ),
            mock.call(
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/frames-######',
                    frames='5')],
                'blender-render-5',
                status='under-construction',
                task_type='blender-render',
                parents=None,
            ),

            # Move to final location
            mock.call(
                job_doc,
                [commands.MoveToFinal(
                    src='/render/out__intermediate-2018-07-06_115233',
                    dest='/render/out')],
                'move-to-final',
                parents=task_ids[0:3],
                status='under-construction',
                task_type='file-management',
            ),
        ])

        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'queued', now=mock_now)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'queued', now=mock_now)

    @mock.patch('datetime.datetime')
    def test_rna_overrides(self, mock_datetime):
        from flamenco.job_compilers import blender_render, commands

        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            '_created': self.created,
            'settings': {
                'frames': '1-5',
                'chunk_size': 2,
                'render_output': '/render/out/frames-######',
                'format': 'EXR',
                'filepath': '/agent327/scenes/someshot/somefile.blend',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',
                'rna_overrides': [
                    'bpy.context.scene.render.stamp_note_text = "je moeder"',
                    'bpy.context.scene.render.use_stamp_note = True',
                    'bpy.context.scene.render.use_stamp = True',
                ],
            },
            'job_type': 'blender-render',
        })

        expect_rna_overrides = '\n'.join([blender_render.RNA_OVERRIDES_HEADER,
                                          *job_doc['settings']['rna_overrides'],
                                          ''])

        task_manager = mock.Mock()
        job_manager = mock.Mock()

        # Create a stable 'now' for testing.
        mock_now = datetime.datetime.now(tz=tz_util.utc)
        mock_datetime.now.side_effect = [mock_now]

        # We expect:
        # - 1 RNA override task
        # - 3 frame chunks of 2 frames each
        # - 1 move-to-final task
        # so that's 5 tasks in total.
        task_ids = [ObjectId() for _ in range(5)]
        task_manager.api_create_task.side_effect = task_ids

        compiler = blender_render.BlenderRender(
            task_manager=task_manager, job_manager=job_manager)
        compiler.compile(job_doc)

        task_manager.api_create_task.assert_has_calls([
            # Override task
            mock.call(
                job_doc,
                [commands.CreatePythonFile(
                    filepath='/agent327/scenes/someshot/somefile-overrides.py',
                    contents=expect_rna_overrides,
                )],
                blender_render.RNA_OVERRIDES_TASK_NAME,
                status='under-construction',
                task_type='file-management',
                parents=None,
            ),
            # Render tasks
            mock.call(
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/frames-######',
                    frames='1,2')],
                'blender-render-1,2',
                status='under-construction',
                task_type='blender-render',
                parents=[task_ids[0]],
            ),
            mock.call(
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/frames-######',
                    frames='3,4')],
                'blender-render-3,4',
                status='under-construction',
                task_type='blender-render',
                parents=[task_ids[0]],
            ),
            mock.call(
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/frames-######',
                    frames='5')],
                'blender-render-5',
                status='under-construction',
                task_type='blender-render',
                parents=[task_ids[0]],
            ),

            # Move to final location
            mock.call(
                job_doc,
                [commands.MoveToFinal(
                    src='/render/out__intermediate-2018-07-06_115233',
                    dest='/render/out')],
                'move-to-final',
                parents=task_ids[1:4],
                status='under-construction',
                task_type='file-management',
            ),
        ])

        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'queued', now=mock_now)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'queued', now=mock_now)

    def test_create_video(self):
        from flamenco.job_compilers import blender_render, commands

        with self.app.app_context():
            self.flamenco.db('managers').update_one(
                {'_id': self.mngr_id},
                {'$set': {'worker_task_types': ['blender-render', 'video-encoding']}}
            )

        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            '_created': self.created,
            'manager': self.mngr_id,
            'settings': {
                'frames': '1-5',
                'chunk_size': 3,
                'render_output': '/render/out/frames-######',
                'format': 'EXR',
                'filepath': '/agent327/scenes/someshot/somefile.flamenco.blend',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',

                # On top of pretty much the same settings as test_small_job(),
                # we add those settings that trigger the creation of the
                # create_video task.
                'fps': 24,
                'images_or_video': 'images',
                'output_file_extension': '.exr',
            },
            'job_type': 'blender-render',
        })

        task_manager = mock.Mock()
        job_manager = mock.Mock()

        # We expect:
        # - 2 chunk of 3 resp 2 frames.
        # - 1 create_video task.
        # - 1 move-to-final task.
        # so that's 4 tasks in total.
        task_ids = [ObjectId() for _ in range(4)]
        task_manager.api_create_task.side_effect = task_ids

        compiler = blender_render.BlenderRender(
            task_manager=task_manager, job_manager=job_manager)

        with self.app.app_context():
            compiler.compile(job_doc)

        task_manager.api_create_task.assert_has_calls([
            # Render tasks
            mock.call(
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.flamenco.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/frames-######',
                    frames='1..3')],
                'blender-render-1-3',
                status='under-construction',
                task_type='blender-render',
                parents=None,
            ),
            mock.call(
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.flamenco.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/frames-######',
                    frames='4,5')],
                'blender-render-4,5',
                status='under-construction',
                task_type='blender-render',
                parents=None,
            ),

            # Create a video of the final frames.
            mock.call(
                job_doc,
                [commands.CreateVideo(
                    input_files='/render/out__intermediate-2018-07-06_115233/*.exr',
                    output_file='/render/out__intermediate-2018-07-06_115233/somefile-1-5.mkv',
                    fps=24,
                    ffmpeg_cmd='{ffmpeg}',
                )],
                'create-video',
                parents=task_ids[0:2],
                status='under-construction',
                task_type='video-encoding',
            ),

            # Move to final location
            mock.call(
                job_doc,
                [commands.MoveToFinal(
                    src='/render/out__intermediate-2018-07-06_115233',
                    dest='/render/out')],
                'move-to-final',
                parents=[task_ids[2]],
                status='under-construction',
                task_type='file-management',
            ),
        ])

        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'queued', now=mock.ANY)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'queued', now=mock.ANY)

    def create_video_without_proper_task_type_support(self):
        from flamenco.job_compilers import blender_render, commands

        with self.app.app_context():
            self.flamenco.db('managers').update_one(
                {'_id': self.mngr_id},
                # No video-encoding task type
                {'$set': {'worker_task_types': ['blender-render']}}
            )

        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            '_created': self.created,
            'manager': self.mngr_id,
            'settings': {
                'frames': '1-5',
                'chunk_size': 3,
                'render_output': '/render/out/frames-######',
                'format': 'EXR',
                'filepath': '/agent327/scenes/someshot/somefile.flamenco.blend',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',

                # On top of pretty much the same settings as test_small_job(),
                # we add those settings that trigger the creation of the
                # create_video task.
                'fps': 24,
                'images_or_video': 'images',
                'output_file_extension': '.exr',
            },
            'job_type': 'blender-render',
        })

        task_manager = mock.Mock()
        job_manager = mock.Mock()

        # We expect:
        # - 2 chunk of 3 resp 2 frames.
        # - 1 create_video task.
        # - 1 move-to-final task.
        # so that's 4 tasks in total.
        task_ids = [ObjectId() for _ in range(4)]
        task_manager.api_create_task.side_effect = task_ids

        compiler = blender_render.BlenderRender(
            task_manager=task_manager, job_manager=job_manager)

        with self.app.app_context():
            compiler.compile(job_doc)

        task_manager.api_create_task.assert_has_calls([
            # Render tasks
            mock.call(
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.flamenco.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/frames-######',
                    frames='1..3')],
                'blender-render-1-3',
                status='under-construction',
                task_type='blender-render',
                parents=None,
            ),
            mock.call(
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.flamenco.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/frames-######',
                    frames='4,5')],
                'blender-render-4,5',
                status='under-construction',
                task_type='blender-render',
                parents=None,
            ),

            # Move to final location
            mock.call(
                job_doc,
                [commands.MoveToFinal(
                    src='/render/out__intermediate-2018-07-06_115233',
                    dest='/render/out')],
                'move-to-final',
                parents=task_ids[1:2],
                status='under-construction',
                task_type='file-management',
            ),
        ])

        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'queued', now=mock.ANY)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'queued', now=mock.ANY)


class BlenderRenderProgressiveTest(unittest.TestCase):
    def setUp(self):
        # Create a timestamp before we start mocking datetime.datetime.
        self.created = datetime.datetime(2018, 7, 6, 11, 52, 33, tzinfo=tz_util.utc)

    def test_chunk_generator(self):
        from flamenco.job_compilers import blender_render_progressive as brp
        cg = brp.ChunkGenerator(400, 100)
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

        cg = brp.ChunkGenerator(30, 3000, uncapped_chunks=3)
        expected = [
            (1, 1),
            (2, 10),
            (11, 30),
        ]
        self.assertEqual(expected, list(cg))

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
                'format': 'EXR',
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

        # We expect:
        # - 1 destroy-intermediate task
        # - 2 frame chunks x 3 sample chunks = 6 render tasks
        # - 4 sample merge tasks
        # - 1 'publish first chunk' task
        # so a total of 12 tasks
        task_ids = [ObjectId() for _ in range(50)]
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
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/render-smpl-0001-0001-######',
                    frames='1..3',
                    cycles_num_chunks=30,
                    cycles_chunk_start=1,
                    cycles_chunk_end=1)],
                'render-smpl1-1-frm1-3',
                priority=0,
                parents=[task_ids[0]],
                status='under-construction',
                task_type='blender-render',
            ),
            mock.call(  # task 2
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/render-smpl-0001-0001-######',
                    frames='4,5',
                    cycles_num_chunks=30,
                    cycles_chunk_start=1,
                    cycles_chunk_end=1)],
                'render-smpl1-1-frm4,5',
                priority=0,
                parents=[task_ids[0]],
                status='under-construction',
                task_type='blender-render',
            ),

            mock.call(  # task 3
                job_doc,
                [commands.ExrSequenceToJpeg(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    exr_glob='/render/out__intermediate-2018-07-06_115233/render-smpl-0001-0001-*.exr',
                    output_pattern='preview-######',
                )],
                'create-preview-images',
                priority=-3,
                parents=task_ids[1:3],
                status='under-construction',
                task_type='blender-render',
            ),
            mock.call(  # task 4
                job_doc,
                [commands.CreateVideo(
                    input_files='/render/out__intermediate-2018-07-06_115233/preview-*.jpg',
                    output_file='/render/out__intermediate-2018-07-06_115233/preview.mkv',
                    fps=5.3,
                )],
                'create-preview-video',
                priority=-3,
                parents=[task_ids[3]],
                status='under-construction',
                task_type='video-encoding',
            ),

            # Second Cycles chunk renders to intermediate directory.
            mock.call(  # task 5
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/render-smpl-0002-0010-######',
                    frames='1..3',
                    cycles_num_chunks=30,
                    cycles_chunk_start=2,
                    cycles_chunk_end=10)],
                'render-smpl2-10-frm1-3',
                priority=-10,
                parents=[task_ids[0]],
                status='under-construction',
                task_type='blender-render',
            ),
            mock.call(  # task 6
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/render-smpl-0002-0010-######',
                    frames='4,5',
                    cycles_num_chunks=30,
                    cycles_chunk_start=2,
                    cycles_chunk_end=10)],
                'render-smpl2-10-frm4,5',
                priority=-10,
                parents=[task_ids[0]],
                status='under-construction',
                task_type='blender-render',
            ),

            # First merge pass, outputs to intermediate directory and copies to output dir
            mock.call(  # task 7
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        blender_cmd='/path/to/blender --enable-new-depsgraph',
                        input1='/render/out__intermediate-2018-07-06_115233/render-smpl-0001-0001-000001.exr',
                        input2='/render/out__intermediate-2018-07-06_115233/render-smpl-0002-0010-000001.exr',
                        output='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-000001.exr',
                        weight1=1,
                        weight2=9,
                    ),
                    commands.MergeProgressiveRenders(
                        blender_cmd='/path/to/blender --enable-new-depsgraph',
                        input1='/render/out__intermediate-2018-07-06_115233/render-smpl-0001-0001-000002.exr',
                        input2='/render/out__intermediate-2018-07-06_115233/render-smpl-0002-0010-000002.exr',
                        output='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-000002.exr',
                        weight1=1,
                        weight2=9,
                    ),
                    commands.MergeProgressiveRenders(
                        blender_cmd='/path/to/blender --enable-new-depsgraph',
                        input1='/render/out__intermediate-2018-07-06_115233/render-smpl-0001-0001-000003.exr',
                        input2='/render/out__intermediate-2018-07-06_115233/render-smpl-0002-0010-000003.exr',
                        output='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-000003.exr',
                        weight1=1,
                        weight2=9,
                    ),
                ],
                'merge-to-smpl10-frm1-3',
                parents=[task_ids[1], task_ids[5]],
                priority=-11,
                status='under-construction',
                task_type='exr-merge',
            ),
            mock.call(  # task 8
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        blender_cmd='/path/to/blender --enable-new-depsgraph',
                        input1='/render/out__intermediate-2018-07-06_115233/render-smpl-0001-0001-000004.exr',
                        input2='/render/out__intermediate-2018-07-06_115233/render-smpl-0002-0010-000004.exr',
                        output='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-000004.exr',
                        weight1=1,
                        weight2=9,
                    ),
                    commands.MergeProgressiveRenders(
                        blender_cmd='/path/to/blender --enable-new-depsgraph',
                        input1='/render/out__intermediate-2018-07-06_115233/render-smpl-0001-0001-000005.exr',
                        input2='/render/out__intermediate-2018-07-06_115233/render-smpl-0002-0010-000005.exr',
                        output='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-000005.exr',
                        weight1=1,
                        weight2=9,
                    ),
                ],
                'merge-to-smpl10-frm4,5',
                parents=[task_ids[2], task_ids[6]],
                priority=-11,
                status='under-construction',
                task_type='exr-merge',
            ),
            mock.call(  # task 9
                job_doc,
                [commands.ExrSequenceToJpeg(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    exr_glob='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-*.exr',
                    output_pattern='preview-######',
                )],
                'create-preview-images',
                priority=-13,
                parents=[task_ids[3], task_ids[7], task_ids[8]],
                status='under-construction',
                task_type='blender-render',
            ),
            mock.call(  # task 10
                job_doc,
                [commands.CreateVideo(
                    input_files='/render/out__intermediate-2018-07-06_115233/preview-*.jpg',
                    output_file='/render/out__intermediate-2018-07-06_115233/preview.mkv',
                    fps=5.3,
                )],
                'create-preview-video',
                priority=-13,
                parents=[task_ids[4], task_ids[9]],
                status='under-construction',
                task_type='video-encoding',
            ),

            # Third Cycles chunk renders to intermediate directory.
            mock.call(  # task 11
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/render-smpl-0011-0030-######',
                    frames='1..3',
                    cycles_num_chunks=30,
                    cycles_chunk_start=11,
                    cycles_chunk_end=30)],
                'render-smpl11-30-frm1-3',
                priority=-20,
                parents=[task_ids[0]],
                status='under-construction',
                task_type='blender-render',
            ),
            mock.call(  # task 12
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate-2018-07-06_115233/render-smpl-0011-0030-######',
                    frames='4,5',
                    cycles_num_chunks=30,
                    cycles_chunk_start=11,
                    cycles_chunk_end=30)],
                'render-smpl11-30-frm4,5',
                priority=-20,
                parents=[task_ids[0]],
                status='under-construction',
                task_type='blender-render',
            ),

            # Final merge pass. Could happen directly to the output directory, but to ensure the
            # intermediate directory shows a complete picture (pun intended), we take a similar
            # approach as earlier merge passes.
            mock.call(  # task 13
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        blender_cmd='/path/to/blender --enable-new-depsgraph',
                        input1='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-000001.exr',
                        input2='/render/out__intermediate-2018-07-06_115233/render-smpl-0011-0030-000001.exr',
                        output='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-000001.exr',
                        weight1=10,
                        weight2=20,
                    ),
                    commands.MergeProgressiveRenders(
                        blender_cmd='/path/to/blender --enable-new-depsgraph',
                        input1='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-000002.exr',
                        input2='/render/out__intermediate-2018-07-06_115233/render-smpl-0011-0030-000002.exr',
                        output='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-000002.exr',
                        weight1=10,
                        weight2=20,
                    ),
                    commands.MergeProgressiveRenders(
                        blender_cmd='/path/to/blender --enable-new-depsgraph',
                        input1='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-000003.exr',
                        input2='/render/out__intermediate-2018-07-06_115233/render-smpl-0011-0030-000003.exr',
                        output='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-000003.exr',
                        weight1=10,
                        weight2=20,
                    ),
                ],
                'merge-to-smpl30-frm1-3',
                parents=[task_ids[7], task_ids[11]],
                priority=-21,
                status='under-construction',
                task_type='exr-merge',
            ),
            mock.call(  # task 14
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        blender_cmd='/path/to/blender --enable-new-depsgraph',
                        input1='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-000004.exr',
                        input2='/render/out__intermediate-2018-07-06_115233/render-smpl-0011-0030-000004.exr',
                        output='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-000004.exr',
                        weight1=10,
                        weight2=20,
                    ),
                    commands.MergeProgressiveRenders(
                        blender_cmd='/path/to/blender --enable-new-depsgraph',
                        input1='/render/out__intermediate-2018-07-06_115233/merge-smpl-0010-000005.exr',
                        input2='/render/out__intermediate-2018-07-06_115233/render-smpl-0011-0030-000005.exr',
                        output='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-000005.exr',
                        weight1=10,
                        weight2=20,
                    ),
                ],
                'merge-to-smpl30-frm4,5',
                parents=[task_ids[8], task_ids[12]],
                priority=-21,
                status='under-construction',
                task_type='exr-merge',
            ),

            mock.call(  # task 15
                job_doc,
                [commands.ExrSequenceToJpeg(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    exr_glob='/render/out__intermediate-2018-07-06_115233/merge-smpl-0030-*.exr',
                    output_pattern='preview-######',
                )],
                'create-preview-images',
                priority=-23,
                parents=[task_ids[9], task_ids[13], task_ids[14]],
                status='under-construction',
                task_type='blender-render',
            ),
            mock.call(  # task 16
                job_doc,
                [commands.CreateVideo(
                    input_files='/render/out__intermediate-2018-07-06_115233/preview-*.jpg',
                    output_file='/render/out__intermediate-2018-07-06_115233/preview.mkv',
                    fps=5.3,
                )],
                'create-preview-video',
                priority=-23,
                parents=[task_ids[10], task_ids[15]],
                status='under-construction',
                task_type='video-encoding',
            ),

            mock.call(  # task 17
                job_doc,
                [
                    commands.MoveOutOfWay(src='/render/out'),
                ],
                'move-outdir-out-of-way',
                priority=-30,
                parents=task_ids[13:15],
                status='under-construction',
                task_type='file-management',
            ),

            mock.call(  # task 18
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
                priority=-31,
                parents=[task_ids[17]],
                status='under-construction',
                task_type='file-management',
            ),
            mock.call(  # task 19
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
                priority=-31,
                parents=[task_ids[15], task_ids[17]],
                status='under-construction',
                task_type='file-management',
            ),
            mock.call(  # task 20
                job_doc,
                [
                    commands.CopyFile(
                        src='/render/out__intermediate-2018-07-06_115233/preview.mkv',
                        dest='/render/out/preview.mkv',
                    ),
                ],
                'publish-video-to-output',
                priority=-31,
                parents=[task_ids[16], task_ids[17]],
                status='under-construction',
                task_type='file-management',
            ),
        ])

        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'queued', now=mock_now)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'queued', now=mock_now)
