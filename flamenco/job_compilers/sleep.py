from .abstract_compiler import AbstractJobCompiler
from . import commands, register_compiler


@register_compiler('sleep')
class Sleep(AbstractJobCompiler):
    """Sleeps for N seconds for each frame chunk."""

    def _compile(self, job: dict):
        from flamenco.utils import iter_frame_range, frame_range_merge

        self._log.info('Compiling job %s', job['_id'])

        job_settings = job['settings']
        task_count = 0
        for chunk_frames in iter_frame_range(job_settings['frames'], job_settings['chunk_size']):
            task_cmds = [
                commands.Echo(message='Preparing to sleep'),
                commands.Sleep(time_in_seconds=job_settings['time_in_seconds']),
            ]
            name = 'sleep-%s' % frame_range_merge(chunk_frames)

            self._create_task(job, task_cmds, name, 'sleep')
            task_count += 1

        self._log.info('Created %i tasks for job %s', task_count, job['_id'])
