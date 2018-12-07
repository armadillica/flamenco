import datetime
from unittest import mock

from bson import ObjectId, tz_util

from abstract_flamenco_test import AbstractFlamencoTest
from test_job_compilers import JobDocForTesting


class BlenderVideoChunksTest(AbstractFlamencoTest):
    def setUp(self):
        super().setUp()

        # Create a timestamp before we start mocking datetime.datetime.
        self.created = datetime.datetime(2018, 7, 6, 11, 52, 33, tzinfo=tz_util.utc)

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']

        self.mock_now = datetime.datetime.now(tz=tz_util.utc)

    def test_mkv(self):
        self._test_for_extension('.mkv')

    def test_mov(self):
        self._test_for_extension('.mov')

    @mock.patch('datetime.datetime')
    def _test_for_extension(self, extension: str, mock_datetime):
        from flamenco.job_compilers import blender_video_chunks, commands

        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            '_created': self.created,
            'settings': {
                'frames': '100-250',
                'fps': 24,
                'chunk_size': 100,
                'render_output': '/tmp/render/spring/export/FILENAME.MKV',
                'filepath': '/spring/edit/sprloing.blend',
                'output_file_extension': extension,
                'images_or_video': 'video',
                'extract_audio': True,
            },
            'job_type': 'blender-video-chunks',
        })

        task_manager = mock.Mock()
        job_manager = mock.Mock()

        # Create a stable 'now' for testing.
        mock_datetime.now.side_effect = [self.mock_now, self.mock_now]

        # We expect:
        # - 1 move-out-of-way task
        # - 2 frame rendering chunks of resp. 100 and 51 frames each
        # - 2 video encoding chunks
        # - 1 concat-videos task
        # - 1 extract-audio task
        # - 1 encode-audio task (because extracting only works to FLAC at the moment)
        # - 1 mux-audio task
        # - 1 move-to-final task
        # so that's 10 tasks in total.
        task_ids = [ObjectId() for _ in range(10)]
        task_manager.api_create_task.side_effect = task_ids

        compiler = blender_video_chunks.BlenderVideoChunks(
            task_manager=task_manager, job_manager=job_manager)
        compiler.compile(job_doc)

        frames = '/tmp/render/spring/export/frames'
        expected_final_output = f'/tmp/render/spring/export/' \
                                f'{self.mock_now:%Y_%m_%d}-sprloing{extension}'
        task_manager.api_create_task.assert_has_calls([
            mock.call(  # 0
                job_doc,
                [commands.MoveOutOfWay(src=frames)],
                'move-out-of-way',
                status='under-construction',
                task_type='file-management',
            ),

            # Chunk (frames + video) tasks
            mock.call(  # 1
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='{blender}',
                    filepath='/spring/edit/sprloing.blend',
                    render_output=f'{frames}/chunk-00100-00199/######.png',
                    format='PNG',
                    frames='100..199')],
                'frame-chunk-100-199',
                status='under-construction',
                task_type='blender-render',
                parents=[task_ids[0]],
            ),
            mock.call(  # 2
                job_doc,
                [commands.CreateVideo(
                    ffmpeg_cmd='{ffmpeg}',
                    input_files=f'{frames}/chunk-00100-00199/*.png',
                    output_file=f'{frames}/chunk-00100-00199{extension}',
                    fps=24)],
                'video-chunk-100-199',
                status='under-construction',
                task_type='video-encoding',
                parents=[task_ids[1]],
            ),
            mock.call(  # 3
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='{blender}',
                    filepath='/spring/edit/sprloing.blend',
                    render_output=f'{frames}/chunk-00200-00250/######.png',
                    format='PNG',
                    frames='200..250')],
                'frame-chunk-200-250',
                status='under-construction',
                task_type='blender-render',
                parents=[task_ids[0]],
            ),
            mock.call(  # 4
                job_doc,
                [commands.CreateVideo(
                    ffmpeg_cmd='{ffmpeg}',
                    input_files=f'{frames}/chunk-00200-00250/*.png',
                    output_file=f'{frames}/chunk-00200-00250{extension}',
                    fps=24)],
                'video-chunk-200-250',
                status='under-construction',
                task_type='video-encoding',
                parents=[task_ids[3]],
            ),

            # Extract & encode the audio
            mock.call(  # 5
                job_doc,
                [commands.BlenderRenderAudio(
                    blender_cmd='{blender}',
                    filepath='/spring/edit/sprloing.blend',
                    render_output=f'{frames}/audio.flac',
                    frame_start=100,
                    frame_end=250)],
                'render-audio',
                status='under-construction',
                task_type='blender-render',
                parents=[task_ids[0]],
            ),
            mock.call(  # 6
                job_doc,
                [commands.EncodeAudio(
                    ffmpeg_cmd='{ffmpeg}',
                    input_file=f'{frames}/audio.flac',
                    codec='aac',
                    bitrate='192k',
                    output_file=f'{frames}/audio.aac',
                )],
                'encode-audio',
                status='under-construction',
                task_type='video-encoding',
                parents=[task_ids[5]],
            ),

            # Create a video of the chunks.
            mock.call(  # 7
                job_doc,
                [commands.ConcatenateVideos(
                    ffmpeg_cmd='{ffmpeg}',
                    input_files=f'{frames}/chunk-*{extension}',
                    output_file=f'{frames}/video.mkv',
                )],
                'concatenate-videos',
                status='under-construction',
                task_type='video-encoding',
                parents=[task_ids[2], task_ids[4]],
            ),

            # Mux the audio into the video.
            mock.call(  # 8
                job_doc,
                [commands.MuxAudio(
                    ffmpeg_cmd='{ffmpeg}',
                    audio_file=f'{frames}/audio.aac',
                    video_file=f'{frames}/video.mkv',
                    output_file=f'{frames}/muxed.mkv',
                )],
                'mux-audio-video',
                status='under-construction',
                task_type='video-encoding',
                parents=[task_ids[6], task_ids[7]],
            ),

            # Move the file to its final place
            mock.call(  # 9
                job_doc,
                [commands.MoveWithCounter(
                    src=f'{frames}/muxed.mkv',
                    dest=expected_final_output,
                )],
                'move-with-counter',
                status='under-construction',
                task_type='file-management',
                parents=[task_ids[8]],
            ),
        ])

        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'queued', now=self.mock_now)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'queued',
                                       now=self.mock_now)

    @mock.patch('datetime.datetime')
    def test_without_audio(self, mock_datetime):
        from flamenco.job_compilers import blender_video_chunks, commands

        extension = '.mkv'
        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            '_created': self.created,
            'settings': {
                'frames': '100-250',
                'fps': 24,
                'chunk_size': 100,
                'render_output': '/tmp/render/spring/export/FILENAME.MKV',
                'filepath': '/spring/edit/sprloing.blend',
                'output_file_extension': extension,
                'images_or_video': 'video',
                'extract_audio': False,
            },
            'job_type': 'blender-video-chunks',
        })

        task_manager = mock.Mock()
        job_manager = mock.Mock()

        # Create a stable 'now' for testing.
        mock_datetime.now.side_effect = [self.mock_now, self.mock_now]

        # We expect:
        # - 1 move-out-of-way task
        # - 2 frame rendering chunks of resp. 100 and 51 frames each
        # - 2 video encoding chunks
        # - 1 concat-videos task
        # - 1 move-to-final task
        # so that's 7 tasks in total.
        task_ids = [ObjectId() for _ in range(7)]
        task_manager.api_create_task.side_effect = task_ids

        compiler = blender_video_chunks.BlenderVideoChunks(
            task_manager=task_manager, job_manager=job_manager)
        compiler.compile(job_doc)

        frames = '/tmp/render/spring/export/frames'
        expected_final_output = f'/tmp/render/spring/export/' \
                                f'{self.mock_now:%Y_%m_%d}-sprloing{extension}'
        task_manager.api_create_task.assert_has_calls([
            mock.call(  # 0
                job_doc,
                [commands.MoveOutOfWay(src=frames)],
                'move-out-of-way',
                status='under-construction',
                task_type='file-management',
            ),

            # Chunk (frames + video) tasks
            mock.call(  # 1
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='{blender}',
                    filepath='/spring/edit/sprloing.blend',
                    render_output=f'{frames}/chunk-00100-00199/######.png',
                    format='PNG',
                    frames='100..199')],
                'frame-chunk-100-199',
                status='under-construction',
                task_type='blender-render',
                parents=[task_ids[0]],
            ),
            mock.call(  # 2
                job_doc,
                [commands.CreateVideo(
                    ffmpeg_cmd='{ffmpeg}',
                    input_files=f'{frames}/chunk-00100-00199/*.png',
                    output_file=f'{frames}/chunk-00100-00199{extension}',
                    fps=24)],
                'video-chunk-100-199',
                status='under-construction',
                task_type='video-encoding',
                parents=[task_ids[1]],
            ),
            mock.call(  # 3
                job_doc,
                [commands.BlenderRender(
                    blender_cmd='{blender}',
                    filepath='/spring/edit/sprloing.blend',
                    render_output=f'{frames}/chunk-00200-00250/######.png',
                    format='PNG',
                    frames='200..250')],
                'frame-chunk-200-250',
                status='under-construction',
                task_type='blender-render',
                parents=[task_ids[0]],
            ),
            mock.call(  # 4
                job_doc,
                [commands.CreateVideo(
                    ffmpeg_cmd='{ffmpeg}',
                    input_files=f'{frames}/chunk-00200-00250/*.png',
                    output_file=f'{frames}/chunk-00200-00250{extension}',
                    fps=24)],
                'video-chunk-200-250',
                status='under-construction',
                task_type='video-encoding',
                parents=[task_ids[3]],
            ),

            # Create a video of the chunks.
            mock.call(  # 5
                job_doc,
                [commands.ConcatenateVideos(
                    ffmpeg_cmd='{ffmpeg}',
                    input_files=f'{frames}/chunk-*{extension}',
                    output_file=f'{frames}/video.mkv',
                )],
                'concatenate-videos',
                status='under-construction',
                task_type='video-encoding',
                parents=[task_ids[2], task_ids[4]],
            ),

            # Move the file to its final place
            mock.call(  # 6
                job_doc,
                [commands.MoveWithCounter(
                    src=f'{frames}/muxed.mkv',
                    dest=expected_final_output,
                )],
                'move-with-counter',
                status='under-construction',
                task_type='file-management',
                parents=[task_ids[5]],
            ),
        ])

        task_manager.api_set_task_status_for_job.assert_called_with(
            job_doc['_id'], 'under-construction', 'queued', now=self.mock_now)
        job_manager.api_set_job_status(job_doc['_id'], 'under-construction', 'queued',
                                       now=self.mock_now)

    def test_output_images(self):
        from flamenco.job_compilers import blender_video_chunks
        from flamenco.exceptions import JobSettingError

        job_doc = JobDocForTesting({
            '_id': ObjectId(24 * 'f'),
            '_created': self.created,
            'settings': {
                'frames': '100-250',
                'chunk_size': 100,
                'render_output': '/render/out/edit-######',
                'filepath': '/spring/edit/edit.blend',
                'blender_cmd': '/path/to/blender --enable-new-depsgraph',
                'output_file_extension': '*.jemoeder',
                'images_or_video': 'image',
                'fps': 24,
                'project_slug': 'spring',
            },
            'job_type': 'blender-video-chunks',
        })

        task_manager = mock.Mock()
        job_manager = mock.Mock()

        compiler = blender_video_chunks.BlenderVideoChunks(
            task_manager=task_manager, job_manager=job_manager)

        with self.assertRaises(JobSettingError):
            compiler.validate_job_settings(job_doc)
