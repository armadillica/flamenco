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

        move_existing_task_id = self._make_move_out_of_way_task(job)
        task_count = 1 + self._make_render_tasks(job, move_existing_task_id)

        self._log.info('Created %i tasks for job %s', task_count, job['_id'])

    def _make_move_out_of_way_task(self, job):
        """Creates a MoveOutOfWay command to back up existing frames, and wraps it in a task.

        :returns: the ObjectId of the created task.
        :rtype: bson.ObjectId
        """

        import os.path

        # The render path contains a filename pattern, most likely '######' or
        # something similar. This has to be removed, so that we end up with
        # the directory that will contain the frames.
        render_dest_dir = os.path.dirname(job['settings']['render_output'])
        cmd = commands.MoveOutOfWay(src=render_dest_dir)

        task_id = self._create_task(job, [cmd], 'move-existing-frames')
        return task_id

    def _make_render_tasks(self, job, parent_task_id):
        """Creates the render tasks for this job.

        :returns: the number of tasks created
        :rtype: int
        """
        from flamenco.utils import iter_frame_range, frame_range_merge

        job_settings = job['settings']

        task_count = 0
        for chunk_frames in iter_frame_range(job_settings['frames'], job_settings['chunk_size']):
            frame_range = frame_range_merge(chunk_frames)
            frame_range_bstyle = frame_range_merge(chunk_frames, blender_style=True)

            task_cmds = [
                commands.BlenderRender(
                    blender_cmd=job_settings['blender_cmd'],
                    filepath=job_settings['filepath'],
                    format=job_settings.get('format'),
                    render_output=job_settings.get('render_output'),
                    frames=frame_range_bstyle)
            ]

            name = 'blender-render-%s' % frame_range
            self._create_task(job, task_cmds, name, parents=[parent_task_id])
            task_count += 1

        return task_count
