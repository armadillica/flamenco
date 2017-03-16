import pathlib
import typing

import bson
from pillar import attrs_extra

from .abstract_compiler import AbstractJobCompiler
from . import commands, register_compiler


@register_compiler('blender-render')
class BlenderRender(AbstractJobCompiler):
    """Basic Blender render job."""
    _log = attrs_extra.log('%s.BlenderRender' % __name__)

    REQUIRED_SETTINGS = ('blender_cmd', 'filepath', 'render_output', 'frames', 'chunk_size')

    def _compile(self, job):
        self._log.info('Compiling job %s', job['_id'])
        self.validate_job_settings(job)

        # The render path contains a filename pattern, most likely '######' or
        # something similar. This has to be removed, so that we end up with
        # the directory that will contain the frames.
        self.render_output = pathlib.PurePath(job['settings']['render_output'])
        self.final_dir = self.render_output.parent
        self.render_dir = self.final_dir.with_name(self.final_dir.name + '__intermediate')

        render_tasks = self._make_render_tasks(job)
        self._make_move_to_final_task(job, render_tasks)

        task_count = len(render_tasks) + 1
        self._log.info('Created %i tasks for job %s', task_count, job['_id'])

    def _make_move_to_final_task(self, job, parent_task_ids: typing.List[bson.ObjectId]) -> bson.ObjectId:
        """Creates a MoveToFinal command to back up existing frames, and wraps it in a task.

        :returns: the ObjectId of the created task.
        """

        cmd = commands.MoveToFinal(
            src=str(self.render_dir),
            dest=str(self.final_dir),
        )

        task_id = self._create_task(job, [cmd], 'move-to-final', parents=parent_task_ids)
        return task_id

    def _make_render_tasks(self, job) -> typing.List[bson.ObjectId]:
        """Creates the render tasks for this job.

        :returns: the list of task IDs.
        """
        from flamenco.utils import iter_frame_range, frame_range_merge

        job_settings = job['settings']

        task_ids = []
        for chunk_frames in iter_frame_range(job_settings['frames'], job_settings['chunk_size']):
            frame_range = frame_range_merge(chunk_frames)
            frame_range_bstyle = frame_range_merge(chunk_frames, blender_style=True)

            task_cmds = [
                commands.BlenderRender(
                    blender_cmd=job_settings['blender_cmd'],
                    filepath=job_settings['filepath'],
                    format=job_settings.get('format'),
                    render_output=str(self.render_dir / self.render_output.name),
                    frames=frame_range_bstyle)
            ]

            name = 'blender-render-%s' % frame_range
            task_ids.append(self._create_task(job, task_cmds, name))

        return task_ids
