import datetime
import pathlib
from unittest import mock

from bson import ObjectId, tz_util

from abstract_flamenco_test import AbstractFlamencoTest
from test_job_compilers import JobDocForTesting


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
