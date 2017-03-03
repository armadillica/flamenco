import unittest
import mock
from bson import ObjectId


class SleepSimpleTest(unittest.TestCase):
    def test_job_compilation(self):
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
        compiler = sleep.Sleep(task_manager=task_manager)
        compiler.compile(job_doc)

        task_manager.api_create_task.assert_has_calls([
            mock.call(
                job_doc,
                [
                    commands.Echo(message='Preparing to sleep'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-1-13',
            ),
            mock.call(
                job_doc,
                [
                    commands.Echo(message='Preparing to sleep'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-14-26',
            ),
            mock.call(
                job_doc,
                [
                    commands.Echo(message='Preparing to sleep'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-27-30,40-44',
            ),
        ])


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


class BlenderRenderProgressiveTest(unittest.TestCase):
    def test_nonexr_job(self):
        from flamenco.job_compilers import blender_render_progressive
        from flamenco.exceptions import JobSettingError

        job_doc = {
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
        }
        task_manager = mock.Mock()
        compiler = blender_render_progressive.BlenderRenderProgressive(task_manager=task_manager)

        self.assertRaises(JobSettingError, compiler.compile, job_doc)

    def test_small_job(self):
        from flamenco.job_compilers import blender_render_progressive, commands

        job_doc = {
            '_id': ObjectId(24 * 'f'),
            'settings': {
                'frames': '1-6',
                'chunk_size': 2,
                'render_output': '/render/out/frames-######',
                'format': 'EXR',
                'filepath': '/agent327/scenes/someshot/somefile.blend',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',
                'cycles_sample_count': 30,
                'cycles_num_chunks': 3,
            }
        }
        task_manager = mock.Mock()

        # We expect:
        # - 1 move-out-of-way task
        # - 3 frame chunks of 2 frames each
        # - 3 progressive renders per frame
        # - 2 merge tasks per frame chunk
        # so that's a 9 render tasks and 6 merge tasks, giving 16 tasks in total.
        task_ids = [ObjectId() for _ in range(16)]
        task_manager.api_create_task.side_effect = task_ids

        compiler = blender_render_progressive.BlenderRenderProgressive(task_manager=task_manager)
        compiler.compile(job_doc)

        task_manager.api_create_task.assert_has_calls([
            mock.call(job_doc,
                      [commands.MoveOutOfWay(src='/render/out')],
                      'move-existing-frames'),

            # First Cycles chunk
            mock.call(
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out/_intermediate/render-smpl-1-10-frm-######',
                    frames='1,2',
                    cycles_num_chunks=3,
                    cycles_chunk=1,
                    cycles_samples_from=1,
                    cycles_samples_to=10)],
                'render-smpl1-10-frm1,2',
                parents=[task_ids[0]],
                priority=0),
            mock.call(
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out/_intermediate/render-smpl-1-10-frm-######',
                    frames='3,4',
                    cycles_num_chunks=3,
                    cycles_chunk=1,
                    cycles_samples_from=1,
                    cycles_samples_to=10)],
                'render-smpl1-10-frm3,4',
                parents=[task_ids[0]],
                priority=0),
            mock.call(
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out/_intermediate/render-smpl-1-10-frm-######',
                    frames='5,6',
                    cycles_num_chunks=3,
                    cycles_chunk=1,
                    cycles_samples_from=1,
                    cycles_samples_to=10)],
                'render-smpl1-10-frm5,6',
                parents=[task_ids[0]],
                priority=0),

            # Second Cycles chunk
            mock.call(
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out/_intermediate/render-smpl-11-20-frm-######',
                    frames='1,2',
                    cycles_num_chunks=3,
                    cycles_chunk=2,
                    cycles_samples_from=11,
                    cycles_samples_to=20)],
                'render-smpl11-20-frm1,2',
                parents=[task_ids[0]],
                priority=-10),
            mock.call(
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out/_intermediate/render-smpl-11-20-frm-######',
                    frames='3,4',
                    cycles_num_chunks=3,
                    cycles_chunk=2,
                    cycles_samples_from=11,
                    cycles_samples_to=20)],
                'render-smpl11-20-frm3,4',
                parents=[task_ids[0]],
                priority=-10),
            mock.call(
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out/_intermediate/render-smpl-11-20-frm-######',
                    frames='5,6',
                    cycles_num_chunks=3,
                    cycles_chunk=2,
                    cycles_samples_from=11,
                    cycles_samples_to=20)],
                'render-smpl11-20-frm5,6',
                parents=[task_ids[0]],
                priority=-10),

            # First merge pass
            mock.call(
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        input1='/render/out/_intermediate/render-smpl-1-10-frm-000001.exr',
                        input2='/render/out/_intermediate/render-smpl-11-20-frm-000001.exr',
                        output='/render/out/_intermediate/merge-smpl-20-frm-000001.exr',
                        weight1=10,
                        weight2=10,
                    ),
                    commands.MergeProgressiveRenders(
                        input1='/render/out/_intermediate/render-smpl-1-10-frm-000002.exr',
                        input2='/render/out/_intermediate/render-smpl-11-20-frm-000002.exr',
                        output='/render/out/_intermediate/merge-smpl-20-frm-000002.exr',
                        weight1=10,
                        weight2=10,
                    ),
                ],
                'merge-to-smpl20-frm1,2',
                parents=[task_ids[1], task_ids[4]],
                priority=-11),
            mock.call(
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        input1='/render/out/_intermediate/render-smpl-1-10-frm-000003.exr',
                        input2='/render/out/_intermediate/render-smpl-11-20-frm-000003.exr',
                        output='/render/out/_intermediate/merge-smpl-20-frm-000003.exr',
                        weight1=10,
                        weight2=10,
                    ),
                    commands.MergeProgressiveRenders(
                        input1='/render/out/_intermediate/render-smpl-1-10-frm-000004.exr',
                        input2='/render/out/_intermediate/render-smpl-11-20-frm-000004.exr',
                        output='/render/out/_intermediate/merge-smpl-20-frm-000004.exr',
                        weight1=10,
                        weight2=10,
                    ),
                ],
                'merge-to-smpl20-frm3,4',
                parents=[task_ids[2], task_ids[5]],
                priority=-11),
            mock.call(
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        input1='/render/out/_intermediate/render-smpl-1-10-frm-000005.exr',
                        input2='/render/out/_intermediate/render-smpl-11-20-frm-000005.exr',
                        output='/render/out/_intermediate/merge-smpl-20-frm-000005.exr',
                        weight1=10,
                        weight2=10,
                    ),
                    commands.MergeProgressiveRenders(
                        input1='/render/out/_intermediate/render-smpl-1-10-frm-000006.exr',
                        input2='/render/out/_intermediate/render-smpl-11-20-frm-000006.exr',
                        output='/render/out/_intermediate/merge-smpl-20-frm-000006.exr',
                        weight1=10,
                        weight2=10,
                    ),
                ],
                'merge-to-smpl20-frm5,6',
                parents=[task_ids[3], task_ids[6]],
                priority=-11),

            # Third Cycles chunk
            mock.call(
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out/_intermediate/render-smpl-21-30-frm-######',
                    frames='1,2',
                    cycles_num_chunks=3,
                    cycles_chunk=3,
                    cycles_samples_from=21,
                    cycles_samples_to=30)],
                'render-smpl21-30-frm1,2',
                parents=[task_ids[0]],
                priority=-20),
            mock.call(
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out/_intermediate/render-smpl-21-30-frm-######',
                    frames='3,4',
                    cycles_num_chunks=3,
                    cycles_chunk=3,
                    cycles_samples_from=21,
                    cycles_samples_to=30)],
                'render-smpl21-30-frm3,4',
                parents=[task_ids[0]],
                priority=-20),
            mock.call(
                job_doc,
                [commands.BlenderRenderProgressive(
                    blender_cmd='/path/to/blender --enable-new-depsgraph',
                    filepath='/agent327/scenes/someshot/somefile.blend',
                    format='EXR',
                    render_output='/render/out/_intermediate/render-smpl-21-30-frm-######',
                    frames='5,6',
                    cycles_num_chunks=3,
                    cycles_chunk=3,
                    cycles_samples_from=21,
                    cycles_samples_to=30)],
                'render-smpl21-30-frm5,6',
                parents=[task_ids[0]],
                priority=-20),

            # Final merge pass
            mock.call(
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        input1='/render/out/_intermediate/merge-smpl-20-frm-000001.exr',
                        input2='/render/out/_intermediate/render-smpl-21-30-frm-000001.exr',
                        output='/render/out/frames-000001.exr',
                        weight1=20,
                        weight2=10,
                    ),
                    commands.MergeProgressiveRenders(
                        input1='/render/out/_intermediate/merge-smpl-20-frm-000002.exr',
                        input2='/render/out/_intermediate/render-smpl-21-30-frm-000002.exr',
                        output='/render/out/frames-000002.exr',
                        weight1=20,
                        weight2=10,
                    ),
                ],
                'merge-to-smpl30-frm1,2',
                parents=[task_ids[7], task_ids[10]],
                priority=-21),
            mock.call(
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        input1='/render/out/_intermediate/merge-smpl-20-frm-000003.exr',
                        input2='/render/out/_intermediate/render-smpl-21-30-frm-000003.exr',
                        output='/render/out/frames-000003.exr',
                        weight1=20,
                        weight2=10,
                    ),
                    commands.MergeProgressiveRenders(
                        input1='/render/out/_intermediate/merge-smpl-20-frm-000004.exr',
                        input2='/render/out/_intermediate/render-smpl-21-30-frm-000004.exr',
                        output='/render/out/frames-000004.exr',
                        weight1=20,
                        weight2=10,
                    ),
                ],
                'merge-to-smpl30-frm3,4',
                parents=[task_ids[8], task_ids[11]],
                priority=-21),
            mock.call(
                job_doc,
                [
                    commands.MergeProgressiveRenders(
                        input1='/render/out/_intermediate/merge-smpl-20-frm-000005.exr',
                        input2='/render/out/_intermediate/render-smpl-21-30-frm-000005.exr',
                        output='/render/out/frames-000005.exr',
                        weight1=20,
                        weight2=10,
                    ),
                    commands.MergeProgressiveRenders(
                        input1='/render/out/_intermediate/merge-smpl-20-frm-000006.exr',
                        input2='/render/out/_intermediate/render-smpl-21-30-frm-000006.exr',
                        output='/render/out/frames-000006.exr',
                        weight1=20,
                        weight2=10,
                    ),
                ],
                'merge-to-smpl30-frm5,6',
                parents=[task_ids[9], task_ids[12]],
                priority=-21),
        ])
