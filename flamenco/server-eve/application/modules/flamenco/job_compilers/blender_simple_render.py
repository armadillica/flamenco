import json

from application.modules.flamenco.utils import frame_range_parse
from application.modules.flamenco.utils import frame_range_merge


class job_compiler():

    @staticmethod
    def compile(job, create_task):
        job_settings = job['settings']
        parser = 'blender_render'

        task_settings = {
            'filepath': job_settings['filepath'],
            'priority': job['priority'],
            'render_settings': job_settings['render_settings'],
            'format': job_settings['format'],
            'command_name': job_settings['command_name'],
        }

        parsed_frames = frame_range_parse(job_settings['frames'])
        chunk_size = job_settings['chunk_size']
        for i in xrange(0, len(parsed_frames), chunk_size):
            task_settings['frames'] = frame_range_merge(
                parsed_frames[i:i + chunk_size])
            name = task_settings['frames']
            create_task(job, task_settings, name, None, parser)
