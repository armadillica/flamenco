import datetime
from pathlib import PurePath
import typing

from bson import ObjectId

from pillar import attrs_extra

from flamenco import exceptions
from . import abstract_compiler, commands, register_compiler


@register_compiler('blender-video-chunks')
class BlenderVideoChunks(abstract_compiler.AbstractJobCompiler):
    """Render video as chunks, then use ffmpeg to merge.

    Creates a render task for each frame chunk, and then merges the output
    files with ffmpeg to produce the final video.

    Intermediary files are created in a subdirectory of the render output path.
    """

    _log = attrs_extra.log('%s.BlenderVideoChunks' % __name__)
    REQUIRED_SETTINGS = ('filepath', 'render_output', 'frames', 'chunk_size',
                         'output_file_extension', 'images_or_video', 'fps',
                         'extract_audio')

    def validate_job_settings(self, job):
        super().validate_job_settings(job)

        if hasattr(job, 'to_dict'):
            job = job.to_dict()

        img_or_vid = job['settings']['images_or_video']
        if img_or_vid != 'video':
            raise exceptions.JobSettingError(
                f'Job {job["_id"]} is rendering {img_or_vid}, but job type requires video')

        extract_audio = job['settings']['extract_audio']
        if not isinstance(extract_audio, bool):
            raise exceptions.JobSettingError(
                f'Job {job["_id"]} setting "extract_audio" is {extract_audio!r},'
                f' expected a boolean')

    def _compile(self, job):
        self._log.info('Compiling job %s', job['_id'])
        self.validate_job_settings(job)

        # For this job type, the filename in the render output is irrelevant.
        self.final_output_dir = PurePath(job['settings']['render_output']).parent
        self.frames_dir = self.final_output_dir / 'frames'

        self.audio_path = self.frames_dir / 'audio.aac'
        self.video_path = self.frames_dir / 'video.mkv'
        self.muxed_path = self.frames_dir / 'muxed.mkv'

        # Determine final output file.
        blendfile = PurePath(job['settings']['filepath'])
        output_file_extension = job['settings']['output_file_extension']
        stem = blendfile.stem.replace('.flamenco', '')
        now = datetime.datetime.now()
        outfname = f'{now:%Y_%m_%d}-{stem}{output_file_extension}'
        self.final_output_path = self.final_output_dir / outfname

        # Construct the tasks.
        moow_tid = self._make_moow_task(job)
        render_tasks, parent_tasks = self._make_render_tasks(job, moow_tid)

        audio_tid = self._make_extract_audio_task(job, [moow_tid])
        video_tid = self._make_concat_video_task(job, parent_tasks)

        final_parent_tid = video_tid
        if audio_tid is not None:
            final_parent_tid = self._make_mux_audio_task(job, [audio_tid, video_tid])
        self._make_move_with_counter_task(job, [final_parent_tid])

        task_count = len(render_tasks) + 3
        if audio_tid is not None:
            task_count += 2
        self._log.info('Created %i tasks for job %s', task_count, job['_id'])

    def _make_moow_task(self, job) -> ObjectId:
        """Make the move-out-of-way task."""

        cmd = commands.MoveOutOfWay(src=str(self.frames_dir))
        return self._create_task(job, [cmd], 'move-out-of-way', 'file-management')

    def _make_render_tasks(self, job, render_parent_tid: ObjectId) \
            -> typing.Tuple[typing.List[ObjectId], typing.List[ObjectId]]:
        """Creates the render tasks for this job.

        :returns: the list of task IDs.
        """
        from flamenco.utils import iter_frame_range, frame_range_merge

        job_settings = job['settings']

        task_ids = []
        parent_task_ids = []

        for chunk_frames in iter_frame_range(job_settings['frames'], job_settings['chunk_size']):
            frame_range = frame_range_merge(chunk_frames)
            frame_range_bstyle = frame_range_merge(chunk_frames, blender_style=True)

            first_frame = chunk_frames[0]
            last_frame = chunk_frames[-1]
            chunk_name = 'chunk-%05d-%05d' % (first_frame, last_frame)
            render_output = self.frames_dir / chunk_name / '######.png'

            # Export to PNG frames.
            task_cmds = [
                commands.BlenderRender(
                    blender_cmd=job_settings.get('blender_cmd', '{blender}'),
                    filepath=job_settings['filepath'],
                    format='PNG',
                    render_output=str(render_output),
                    frames=frame_range_bstyle,
                )
            ]
            name = 'frame-chunk-%s' % frame_range
            render_task_id = self._create_task(job, task_cmds, name, 'blender-render',
                                               parents=[render_parent_tid])
            task_ids.append(render_task_id)

            # Encode PNG frames to video.
            file_extension = job_settings['output_file_extension']
            task_cmds = [
                commands.CreateVideo(
                    input_files=str(render_output.with_name('*.png')),
                    output_file=str(self.frames_dir / (chunk_name + file_extension)),
                    fps=job_settings['fps'],
                )
            ]
            name = 'video-chunk-%s' % frame_range
            encoding_task_id = self._create_task(job, task_cmds, name, 'video-encoding',
                                                 parents=[render_task_id])
            task_ids.append(encoding_task_id)
            parent_task_ids.append(encoding_task_id)

        return task_ids, parent_task_ids

    def _make_concat_video_task(self, job, parent_task_ids: typing.List[ObjectId]) \
            -> ObjectId:
        """Creates a MergeVideos command to merge the separate video chunks.

        :returns: the ObjectId of the created task.
        """

        job_settings = job['settings']
        output_file_extension = job_settings['output_file_extension']

        cmd = commands.ConcatenateVideos(
            input_files=str(self.frames_dir / f'chunk-*{output_file_extension}'),
            output_file=str(self.video_path),
        )

        return self._create_task(job, [cmd], 'concatenate-videos', 'video-encoding',
                                 parents=parent_task_ids)

    def _make_extract_audio_task(self, job, parent_task_ids: typing.List[ObjectId]) \
            -> typing.Optional[ObjectId]:
        job_settings = job['settings']
        if not job_settings.get('extract_audio', False):
            return None

        from flamenco.utils import frame_range_start_end

        # BIG FAT ASSUMPTION that the frame range is continuous.
        frame_start, frame_end = frame_range_start_end(job_settings['frames'])

        flac_file = self.audio_path.with_suffix('.flac')
        cmd = commands.BlenderRenderAudio(
            blender_cmd=job_settings.get('blender_cmd', '{blender}'),
            filepath=job_settings['filepath'],
            render_output=str(flac_file),
            frame_start=frame_start,
            frame_end=frame_end,
        )
        extract_tid = self._create_task(job, [cmd], 'render-audio', 'blender-render',
                                        parents=parent_task_ids)

        cmd = commands.EncodeAudio(
            input_file=str(flac_file),
            output_file=str(self.audio_path),
            # Hard-coded for now:
            codec='aac',
            bitrate='192k',
        )
        return self._create_task(job, [cmd], 'encode-audio', 'video-encoding',
                                 parents=[extract_tid])

    def _make_mux_audio_task(self, job, parent_task_ids: typing.List[ObjectId]) \
            -> ObjectId:

        cmd = commands.MuxAudio(
            audio_file=str(self.audio_path),
            video_file=str(self.video_path),
            output_file=str(self.muxed_path),
        )
        return self._create_task(job, [cmd], 'mux-audio-video', 'video-encoding',
                                 parents=parent_task_ids)

    def _make_move_with_counter_task(self, job, parent_task_ids: typing.List[ObjectId]) \
            -> ObjectId:
        cmd = commands.MoveWithCounter(
            src=str(self.muxed_path),
            dest=str(self.final_output_path),
        )
        return self._create_task(job, [cmd], 'move-with-counter', 'file-management',
                                 parents=parent_task_ids)
