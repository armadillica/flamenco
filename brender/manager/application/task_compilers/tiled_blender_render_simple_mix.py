import os
import json
import logging

from application import app


class task_compiler():
    @staticmethod
    def compile(worker, task, add_file):

        settings = json.loads(task['settings'])

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
            output_path = settings['output_path_linux']"""


        # TODO
        #file_path = os.path.split(settings['file_path_linux'])[1]
        file_path = os.path.join('==jobpath==', settings['filepath'])
        output_path = "==outputpath=="
        blender_path = "==command=="

        """if setting_render_settings is None:
            logging.warning("Render settings path not set!")
            return None"""

        tiles_path = "tiled_{{0}}_{0:04d}.exr".format(settings['frame_start'])

        # render_settings = os.path.join(
        #     setting_render_settings,
        #     settings['render_settings'])

        # for tile in range(0, settings['tiles']):
        script_path = os.path.join('==jobpath==', 'tile_mix.py')

        dir = os.path.dirname(__file__)
        template_path = os.path.join(
            dir, 'tiled_blender_render_simple_mix.template')
        with open(template_path, "r") as f:
            script = f.read()
        f.close()

        data = """
tiles_path = '{0}'
tiles={1}
tiles_path = os.path.join(os.environ['WORKER_JOBPATH'], '{0}')
        """.format(tiles_path, settings['tiles'])

        script = script.replace("##VARS_INSERTED_HERE##", data)

        add_file(script, 'tile_mix.py', task['job_id'])

        # try:
        #     os.mkdir(output_path)
        # except:
        #     pass

        # f = open(script_path, "w")
        # f.write(script)
        # f.close()

        task_command = [
            str(blender_path),
            '--background',
            '-noaudio',
            str(file_path),
            '--render-output',
            str(os.path.join(output_path, "")),
            '--python',
            str(script_path),
            '--frame-start',
            str(settings['frame_start']),
            '--frame-end',
            str(settings['frame_end']),
            '--render-format',
            str(settings['format']),
            '--render-anim',
            '--enable-autoexec'
        ]

        return task_command
