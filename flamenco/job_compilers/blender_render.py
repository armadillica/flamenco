import pathlib
import typing

import bson
from pillar import attrs_extra

from flamenco import current_flamenco, exceptions
from .abstract_compiler import AbstractJobCompiler
from . import commands, register_compiler


def intermediate_path(job: dict, render_path: pathlib.PurePath) -> pathlib.PurePath:
    """Determine the intermediate render output path."""

    name = f'{render_path.name}__intermediate-{job["_created"]:%Y-%m-%d_%H%M%S}'
    return render_path.with_name(name)


@register_compiler('blender-render')
class BlenderRender(AbstractJobCompiler):
    """Basic Blender render job."""
    _log = attrs_extra.log('%s.BlenderRender' % __name__)

    REQUIRED_SETTINGS = ('filepath', 'render_output', 'frames', 'chunk_size')

    def validate_job_settings(self, job):
        super().validate_job_settings(job)

        if hasattr(job, 'to_dict'):
            job = job.to_dict()

        fps = job['settings'].get('fps')
        if fps is not None and not isinstance(fps, (int, float)):
            raise exceptions.JobSettingError(
                f'Job {job["_id"]} has non-numerical "fps" setting {fps!r}')

    def _compile(self, job):
        self._log.info('Compiling job %s', job['_id'])
        self.validate_job_settings(job)

        # The render path contains a filename pattern, most likely '######' or
        # something similar. This has to be removed, so that we end up with
        # the directory that will contain the frames.
        self.render_output = pathlib.PurePath(job['settings']['render_output'])
        self.final_dir = self.render_output.parent
        self.render_dir = intermediate_path(job, self.final_dir)

        render_tasks, parent_tasks = self._make_render_tasks(job)
        create_video_task = self._make_create_video_task(job, parent_tasks)

        if create_video_task is None:
            final_parents = parent_tasks
        else:
            final_parents = [create_video_task]
        self._make_move_to_final_task(job, final_parents)

        task_count = len(render_tasks) + 1 + (create_video_task is not None)
        self._log.info('Created %i tasks for job %s', task_count, job['_id'])

    def _make_move_to_final_task(self, job,
                                 parent_task_ids: typing.List[bson.ObjectId]) -> bson.ObjectId:
        """Creates a MoveToFinal command to back up existing frames, and wraps it in a task.

        :returns: the ObjectId of the created task.
        """

        cmd = commands.MoveToFinal(
            src=str(self.render_dir),
            dest=str(self.final_dir),
        )

        task_id = self._create_task(job, [cmd], 'move-to-final', 'file-management',
                                    parents=parent_task_ids)
        return task_id

    def _make_create_video_task(self, job, parent_task_ids: typing.List[bson.ObjectId]) \
            -> typing.Optional[bson.ObjectId]:
        """Creates a CreateVideo command to render a video, and wraps it in a task.

        :returns: the ObjectId of the created task, or None if this task should not
            be created for this job.
        """

        job_id: bson.ObjectId = job['_id']
        job_settings = job['settings']
        if hasattr(job_settings, 'to_dict'):
            # Convert from PillarSDK Resource to a dictionary.
            job_settings = job_settings.to_dict()

        # Check whether we should create this task at all.
        images_or_video = job_settings.get('images_or_video', '-not set-')
        if images_or_video != 'images':
            self._log.debug('Not creating create-video task for job %s with images_or_video=%s',
                            job_id, images_or_video)
            return None

        try:
            fps = job_settings['fps']
        except KeyError:
            self._log.debug('Not creating create-video task for job %s without fps setting', job_id)
            return None

        try:
            output_file_extension = job_settings['output_file_extension']
        except KeyError:
            self._log.debug('Not creating create-video task for job %s without '
                            'output_file_extension setting', job_id)
            return None

        # Check the Manager to see if the task type we need is supported at all.
        manager_id: bson.ObjectId = job.get('manager')
        if not manager_id:
            self._log.error('Job %s is not assigned to a manager; not creating create-video task',
                            job_id)
            return None
        manager = current_flamenco.db('managers').find_one(
            manager_id, projection={'worker_task_types': 1})
        if not manager:
            self._log.error('Job %s has non-existant manager %s; not creating create-video task',
                            job_id, manager_id)
            return None
        if 'worker_task_types' not in manager:
            self._log.info('Manager %s for job %s has no known worker task types; '
                           'not creating create-video task', job_id, manager_id)
            return None
        if 'video-encoding' not in manager['worker_task_types']:
            self._log.info('Manager %s for job %s does not support the video-encoding task type; '
                           'not creating create-video task', job_id, manager_id)
            return None

        blendfile = pathlib.Path(job_settings['filepath'])
        stem = blendfile.stem.replace('.flamenco', '')
        outfile = self.render_dir / f'{stem}-{job_settings["frames"]}.mkv'

        cmd = commands.CreateVideo(
            input_files=str(self.render_dir / f'*{output_file_extension}'),
            output_file=str(outfile),
            fps=fps,
        )

        task_id = self._create_task(job, [cmd], 'create-video', 'video-encoding',
                                    parents=parent_task_ids)
        return task_id

    def _make_render_tasks(self, job) \
            -> typing.Tuple[typing.List[bson.ObjectId], typing.List[bson.ObjectId]]:
        """Creates the render tasks for this job.

        :returns: two lists of task IDs: (all tasks, parent tasks for next command)
        """
        from flamenco.utils import iter_frame_range, frame_range_merge

        job_settings = job['settings']

        task_ids = []
        for chunk_frames in iter_frame_range(job_settings['frames'], job_settings['chunk_size']):
            frame_range = frame_range_merge(chunk_frames)
            frame_range_bstyle = frame_range_merge(chunk_frames, blender_style=True)

            task_cmds = [
                commands.BlenderRender(
                    blender_cmd=job_settings.get('blender_cmd', '{blender}'),
                    filepath=job_settings['filepath'],
                    format=job_settings.get('format'),
                    render_output=str(self.render_dir / self.render_output.name),
                    frames=frame_range_bstyle)
            ]

            name = 'blender-render-%s' % frame_range
            task_ids.append(self._create_task(job, task_cmds, name, 'blender-render'))

        return task_ids, task_ids
