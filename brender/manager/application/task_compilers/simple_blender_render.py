import os
import json
#import logging

#from application import app

class task_compiler():
    @staticmethod
    def compile(worker, task, add_file):

        settings=json.loads(task['settings'])

        """if 'Darwin' in worker.system:
            setting_blender_path = app.config['BLENDER_PATH_OSX']
            setting_render_settings = app.config['SETTINGS_PATH_OSX']
            file_path = settings['file_path_osx']
            output_path = settings['output_path_osx']
        elif 'Windows' in worker.system:
            setting_blender_path = app.config['BLENDER_PATH_WIN']
            setting_render_settings = app.config['SETTINGS_PATH_WIN']
            file_path = settings['file_path_win']
            output_path = settings['output_path_win']
        elif 'Linux' in worker.system:
            setting_blender_path = app.config['BLENDER_PATH_LINUX']
            setting_render_settings = app.config['SETTINGS_PATH_LINUX']
            file_path = settings['file_path_linux']
            output_path = settings['output_path_linux']

        if setting_blender_path is None:
            logging.info('[Debug] blender path is not set')
            return None

        if setting_render_settings is None:
            logging.warning("Render settings path not set!")
            return None

        setting_render_settings = app.config['SETTINGS_PATH_LINUX']
        render_settings = os.path.join(
            setting_render_settings,
            settings['render_settings'])"""

        # TODO
        file_path = os.path.split(settings['file_path_linux'])[1]
        file_path = os.path.join('==jobpath==', file_path)
        output_path = "==outputpath=="

        blender_path = "==blenderpath=="

        dir = os.path.dirname(__file__)
        template_path = os.path.join(dir, 'simple_blender_render.template')
        with open(template_path, "r") as f:
            script = f.read()
        f.close()


        add_file(
            script,
            'pre_render.py',
            task['job_id']
        )


        script_path = os.path.join(
            "==jobpath==", "pre_render.py")

        output_path = os.path.join("==outputpath==", "####")

        task_command = [
        str( blender_path ),
        '-noaudio',
        '--background',
        str( file_path ),
        '--render-output',
        str(output_path),
        '--python',
        str(script_path),
        '--frame-start' ,
        str(settings['frame_start']),
        '--frame-end',
        str(settings['frame_end']),
        '--render-format',
        str(settings['format']),
        '--render-anim',
        '--enable-autoexec'
        ]

        return task_command
