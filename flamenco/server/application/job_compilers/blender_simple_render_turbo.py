import os
import json
import logging

from application.utils import frame_range_parse
from application.utils import frame_range_merge


class job_compiler():

    @staticmethod
    def compile(job, project, create_task):
        job_settings = json.loads(job.settings)
        task_type = 'blender_simple_render_turbo'
        parser = 'blender_render'

        task_settings = {}
        task_settings['filepath'] = job_settings['filepath']
        task_settings['priority'] = job.priority
        task_settings['render_settings'] = job_settings['render_settings']
        task_settings['format'] = job_settings['format']
        task_settings['command_name'] = job_settings['command_name']

        task_settings['file_path_linux'] = ""
        task_settings['file_path_win'] = ""
        task_settings['file_path_osx'] = ""

        task_settings['output_path_linux'] = '#####'
        task_settings['output_path_win'] = '#####'
        task_settings['output_path_osx'] = '#####'


        parsed_frames = frame_range_parse(job_settings['frames'])
        chunk_size = job_settings['chunk_size']

        for i in xrange(0, len(parsed_frames), chunk_size):
            task_settings['frames'] = frame_range_merge(parsed_frames[i:i + chunk_size])
            name = task_settings['frames']
            create_task(job.id, task_type, task_settings, name, None, parser)
