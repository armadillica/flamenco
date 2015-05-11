import os
import json
import logging

class job_compiler():
    @staticmethod
    def compile(job, project, create_task):
        job_settings = json.loads(job.settings)
        task_type='blender_bake_anim_cache'
        parser='blender_render'

        task_settings={}
        task_settings['filepath'] = job_settings['filepath']
        task_settings['render_settings'] = job_settings['render_settings']
        task_settings['format'] = job_settings['format']
        task_settings['command_name'] = job_settings['command_name']

        task_settings['file_path_linux'] = ""
        task_settings['file_path_win'] = ""
        task_settings['file_path_osx'] = ""

        task_settings['output_path_linux'] = '#####'
        task_settings['output_path_win'] = '#####'
        task_settings['output_path_osx'] = '#####'
        task_settings['priority'] = job.priority

        name = "Bake Anim Cache - {0}".format(job_settings['filepath'])

        create_task(job.id, task_type, task_settings, name, None, parser)
