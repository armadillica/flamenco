import datetime
import logging
import unittest
from unittest import mock

from bson import ObjectId, tz_util


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
        from flamenco.job_compilers import sleep, commands

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

        task_manager.api_create_task.assert_has_calls([
            mock.call(
                job_doc,
                [
                    commands.Echo(message='Preparing to sleep'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-1-13',
                status='under-construction',
            ),
            mock.call(
                job_doc,
                [
                    commands.Echo(message='Preparing to sleep'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-14-26',
                status='under-construction',
            ),
            mock.call(
                job_doc,
                [
                    commands.Echo(message='Preparing to sleep'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-27-30,40-44',
                status='under-construction',
            ),
        ])

        # Both calls should be performed with the same 'now'.
        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'queued', now=mock_now)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'queued', now=mock_now)


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


class BlenderRenderTest(unittest.TestCase):
    @mock.patch('datetime.datetime')
    def test_small_job(self, mock_datetime):
        from flamenco.job_compilers import blender_render, commands

        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            'settings': {
                'frames': '1-5',
                'chunk_size': 2,
                'render_output': '/render/out/frames-######',
                'format': 'EXR',
                'filepath': '/agent327/scenes/someshot/somefile.blend',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',
            }
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
                    render_output='/render/out__intermediate/frames-######',
                    frames='1,2')],
                'blender-render-1,2',
                status='under-construction'),
            mock.call(
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate/frames-######',
                    frames='3,4')],
                'blender-render-3,4',
                status='under-construction'),
            mock.call(
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate/frames-######',
                    frames='5')],
                'blender-render-5',
                status='under-construction'),

            # Move to final location
            mock.call(
                job_doc,
                [commands.MoveToFinal(
                    src='/render/out__intermediate',
                    dest='/render/out')],
                'move-to-final',
                parents=task_ids[0:3],
                status='under-construction'),
        ])

        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'queued', now=mock_now)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'queued', now=mock_now)


class BlenderRenderProgressiveTest(unittest.TestCase):
    def test_nonexr_job(self):
        from flamenco.job_compilers import blender_render_progressive
        from flamenco.exceptions import JobSettingError

        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            'settings': {
                'frames': '1-6',
                'chunk_size': 2,
                'render_output': '/render/out/frames-######',
                'format': 'JPEG',
                'filepath': '/agent327/scenes/someshot/somefile.blend',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',
                'cycles_sample_count': 30,
                'cycles_num_chunks': 3,
            }
        })
        task_manager = mock.Mock()
        job_manager = mock.Mock()
        compiler = blender_render_progressive.BlenderRenderProgressive(
            task_manager=task_manager, job_manager=job_manager)

        self.assertRaises(JobSettingError, compiler.compile, job_doc)

    @mock.patch('datetime.datetime')
    def test_small_job(self, mock_datetime):
        from flamenco.job_compilers import blender_render_progressive, commands

        logging.basicConfig(level=logging.DEBUG)

        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            'settings': {
                'frames': '1-5',
                'chunk_size': 2,
                'render_output': '/render/out/frames-######',
                'format': 'EXR',
                'filepath': '/agent327/scenes/someshot/somefile.blend',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',
                'cycles_sample_count': 30,
                'cycles_num_chunks': 3,
            }
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
        compiler.compile(job_doc)

        task_manager.api_create_task.assert_has_calls([
            # Pre-existing intermediate directory is destroyed.
            mock.call(  # task 0
                job_doc,
                [commands.RemoveTree(path='/render/out__intermediate')],
                'destroy-preexisting-intermediate',
                status='under-construction'),

            # First Cycles chunk goes into intermediate directory
            mock.call(  # task 1
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate/render-smpl-0001-0010-frm-######',
                    frames='1,2',
                    cycles_num_chunks=3,
                    cycles_chunk=1,
                    cycles_samples_from=1,
                    cycles_samples_to=10)],
                'render-smpl1-10-frm1,2',
                priority=0,
                parents=[task_ids[0]],
                status='under-construction'),
            mock.call(  # task 2
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate/render-smpl-0001-0010-frm-######',
                    frames='3,4',
                    cycles_num_chunks=3,
                    cycles_chunk=1,
                    cycles_samples_from=1,
                    cycles_samples_to=10)],
                'render-smpl1-10-frm3,4',
                priority=0,
                parents=[task_ids[0]],
                status='under-construction'),
            mock.call(  # task 3
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate/render-smpl-0001-0010-frm-######',
                    frames='5',
                    cycles_num_chunks=3,
                    cycles_chunk=1,
                    cycles_samples_from=1,
                    cycles_samples_to=10)],
                'render-smpl1-10-frm5',
                priority=0,
                parents=[task_ids[0]],
                status='under-construction'),

            # Pre-existing render output dir is moved aside, and intermediate is destroyed.
            # Copy first sample chunk of frames to the output directory.
            mock.call(  # task 4
                job_doc,
                [
                    commands.MoveOutOfWay(src='/render/out'),
                    commands.CopyFile(
                        src='/render/out__intermediate/render-smpl-0001-0010-frm-000001.exr',
                        dest='/render/out/frames-000001.exr',
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/render-smpl-0001-0010-frm-000002.exr',
                        dest='/render/out/frames-000002.exr',
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/render-smpl-0001-0010-frm-000003.exr',
                        dest='/render/out/frames-000003.exr',
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/render-smpl-0001-0010-frm-000004.exr',
                        dest='/render/out/frames-000004.exr',
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/render-smpl-0001-0010-frm-000005.exr',
                        dest='/render/out/frames-000005.exr',
                    ),
                ],
                'publish-first-chunk',
                parents=task_ids[1:4],
                status='under-construction'),

            # Second Cycles chunk renders to intermediate directory.
            mock.call(  # task 5
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate/render-smpl-0011-0020-frm-######',
                    frames='1,2',
                    cycles_num_chunks=3,
                    cycles_chunk=2,
                    cycles_samples_from=11,
                    cycles_samples_to=20)],
                'render-smpl11-20-frm1,2',
                priority=-10,
                parents=[task_ids[0]],
                status='under-construction'),
            mock.call(  # task 6
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate/render-smpl-0011-0020-frm-######',
                    frames='3,4',
                    cycles_num_chunks=3,
                    cycles_chunk=2,
                    cycles_samples_from=11,
                    cycles_samples_to=20)],
                'render-smpl11-20-frm3,4',
                priority=-10,
                parents=[task_ids[0]],
                status='under-construction'),
            mock.call(  # task 7
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate/render-smpl-0011-0020-frm-######',
                    frames='5',
                    cycles_num_chunks=3,
                    cycles_chunk=2,
                    cycles_samples_from=11,
                    cycles_samples_to=20)],
                'render-smpl11-20-frm5',
                priority=-10,
                parents=[task_ids[0]],
                status='under-construction'),

            # First merge pass, outputs to intermediate directory and copies to output dir
            mock.call(  # task 8
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        input1='/render/out__intermediate/render-smpl-0001-0010-frm-000001.exr',
                        input2='/render/out__intermediate/render-smpl-0011-0020-frm-000001.exr',
                        output='/render/out__intermediate/merge-smpl-0020-frm-000001.exr',
                        weight1=10,
                        weight2=10,
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/merge-smpl-0020-frm-000001.exr',
                        dest='/render/out/frames-000001.exr',
                    ),
                    commands.MergeProgressiveRenders(
                        input1='/render/out__intermediate/render-smpl-0001-0010-frm-000002.exr',
                        input2='/render/out__intermediate/render-smpl-0011-0020-frm-000002.exr',
                        output='/render/out__intermediate/merge-smpl-0020-frm-000002.exr',
                        weight1=10,
                        weight2=10,
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/merge-smpl-0020-frm-000002.exr',
                        dest='/render/out/frames-000002.exr',
                    ),
                ],
                'merge-to-smpl20-frm1,2',
                parents=[task_ids[4], task_ids[5]],
                priority=-11,
                status='under-construction'),
            mock.call(  # task 9
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        input1='/render/out__intermediate/render-smpl-0001-0010-frm-000003.exr',
                        input2='/render/out__intermediate/render-smpl-0011-0020-frm-000003.exr',
                        output='/render/out__intermediate/merge-smpl-0020-frm-000003.exr',
                        weight1=10,
                        weight2=10,
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/merge-smpl-0020-frm-000003.exr',
                        dest='/render/out/frames-000003.exr',
                    ),
                    commands.MergeProgressiveRenders(
                        input1='/render/out__intermediate/render-smpl-0001-0010-frm-000004.exr',
                        input2='/render/out__intermediate/render-smpl-0011-0020-frm-000004.exr',
                        output='/render/out__intermediate/merge-smpl-0020-frm-000004.exr',
                        weight1=10,
                        weight2=10,
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/merge-smpl-0020-frm-000004.exr',
                        dest='/render/out/frames-000004.exr',
                    ),
                ],
                'merge-to-smpl20-frm3,4',
                parents=[task_ids[4], task_ids[6]],
                priority=-11,
                status='under-construction'),
            mock.call(  # task 10
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        input1='/render/out__intermediate/render-smpl-0001-0010-frm-000005.exr',
                        input2='/render/out__intermediate/render-smpl-0011-0020-frm-000005.exr',
                        output='/render/out__intermediate/merge-smpl-0020-frm-000005.exr',
                        weight1=10,
                        weight2=10,
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/merge-smpl-0020-frm-000005.exr',
                        dest='/render/out/frames-000005.exr',
                    ),
                ],
                'merge-to-smpl20-frm5',
                parents=[task_ids[4], task_ids[7]],
                priority=-11,
                status='under-construction'),

            # Third Cycles chunk renders to intermediate directory.
            mock.call(  # task 11
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate/render-smpl-0021-0030-frm-######',
                    frames='1,2',
                    cycles_num_chunks=3,
                    cycles_chunk=3,
                    cycles_samples_from=21,
                    cycles_samples_to=30)],
                'render-smpl21-30-frm1,2',
                priority=-20,
                parents=[task_ids[0]],
                status='under-construction'),
            mock.call(  # task 12
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate/render-smpl-0021-0030-frm-######',
                    frames='3,4',
                    cycles_num_chunks=3,
                    cycles_chunk=3,
                    cycles_samples_from=21,
                    cycles_samples_to=30)],
                'render-smpl21-30-frm3,4',
                priority=-20,
                parents=[task_ids[0]],
                status='under-construction'),
            mock.call(  # task 13
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out__intermediate/render-smpl-0021-0030-frm-######',
                    frames='5',
                    cycles_num_chunks=3,
                    cycles_chunk=3,
                    cycles_samples_from=21,
                    cycles_samples_to=30)],
                'render-smpl21-30-frm5',
                priority=-20,
                parents=[task_ids[0]],
                status='under-construction'),

            # Final merge pass. Could happen directly to the output directory, but to ensure the
            # intermediate directory shows a complete picture (pun intended), we take a similar
            # approach as earlier merge passes.
            mock.call(  # task 14
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        input1='/render/out__intermediate/merge-smpl-0020-frm-000001.exr',
                        input2='/render/out__intermediate/render-smpl-0021-0030-frm-000001.exr',
                        output='/render/out__intermediate/merge-smpl-0030-frm-000001.exr',
                        weight1=20,
                        weight2=10,
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/merge-smpl-0030-frm-000001.exr',
                        dest='/render/out/frames-000001.exr',
                    ),
                    commands.MergeProgressiveRenders(
                        input1='/render/out__intermediate/merge-smpl-0020-frm-000002.exr',
                        input2='/render/out__intermediate/render-smpl-0021-0030-frm-000002.exr',
                        output='/render/out__intermediate/merge-smpl-0030-frm-000002.exr',
                        weight1=20,
                        weight2=10,
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/merge-smpl-0030-frm-000002.exr',
                        dest='/render/out/frames-000002.exr',
                    ),
                ],
                'merge-to-smpl30-frm1,2',
                parents=[task_ids[8], task_ids[11]],
                priority=-21,
                status='under-construction'),
            mock.call(  # task 15
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        input1='/render/out__intermediate/merge-smpl-0020-frm-000003.exr',
                        input2='/render/out__intermediate/render-smpl-0021-0030-frm-000003.exr',
                        output='/render/out__intermediate/merge-smpl-0030-frm-000003.exr',
                        weight1=20,
                        weight2=10,
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/merge-smpl-0030-frm-000003.exr',
                        dest='/render/out/frames-000003.exr',
                    ),
                    commands.MergeProgressiveRenders(
                        input1='/render/out__intermediate/merge-smpl-0020-frm-000004.exr',
                        input2='/render/out__intermediate/render-smpl-0021-0030-frm-000004.exr',
                        output='/render/out__intermediate/merge-smpl-0030-frm-000004.exr',
                        weight1=20,
                        weight2=10,
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/merge-smpl-0030-frm-000004.exr',
                        dest='/render/out/frames-000004.exr',
                    ),
                ],
                'merge-to-smpl30-frm3,4',
                parents=[task_ids[9], task_ids[12]],
                priority=-21,
                status='under-construction'),
            mock.call(  # task 16
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        input1='/render/out__intermediate/merge-smpl-0020-frm-000005.exr',
                        input2='/render/out__intermediate/render-smpl-0021-0030-frm-000005.exr',
                        output='/render/out__intermediate/merge-smpl-0030-frm-000005.exr',
                        weight1=20,
                        weight2=10,
                    ),
                    commands.CopyFile(
                        src='/render/out__intermediate/merge-smpl-0030-frm-000005.exr',
                        dest='/render/out/frames-000005.exr',
                    ),
                ],
                'merge-to-smpl30-frm5',
                parents=[task_ids[10], task_ids[13]],
                priority=-21,
                status='under-construction'),
        ])

        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'queued', now=mock_now)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'queued', now=mock_now)
