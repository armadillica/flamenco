import os.path

from .abstract_compiler import AbstractJobCompiler
from . import commands, register_compiler


@register_compiler('blender-render')
class BlenderRender(AbstractJobCompiler):
    """Basic Blender render job."""

    def compile(self, job):
        from flamenco.utils import iter_frame_range, frame_range_merge

        self._log.info('Compiling job %s', job['_id'])

        job_settings = job['settings']

        task_count = 0
        for chunk_frames in iter_frame_range(job_settings['frames'], job_settings['chunk_size']):
            frame_range = frame_range_merge(chunk_frames)
            frame_range_bstyle = frame_range_merge(chunk_frames, blender_style=True)

            task_cmds = [
                commands.BlenderRender(
                    filepath=job_settings['filepath'],
                    format=job_settings.get('format'),
                    render_output=job_settings.get('render_output'),
                    frames=frame_range_bstyle)
            ]

            name = 'blender-render-%s' % frame_range
            self.task_manager.api_create_task(job, task_cmds, name)
            task_count += 1

        self._log.info('Created %i tasks for job %s', task_count, job['_id'])
