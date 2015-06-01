import os
import json
#import logging

#from application import app

class task_compiler():
    @staticmethod
    def compile(worker, task, add_file):

        settings=task['settings']

        # TODO
        file_path = os.path.join('==jobpath==', settings['filepath'])
        output_path = "==outputpath=="

        blender_path = "==command=="

        dir = os.path.dirname(__file__)
        template_path = os.path.join(dir, 'blender_opengl_render.template')
        with open(template_path, "r") as f:
            script = f.read()
        f.close()

        add_file(
            script,
            'blender_opengl_render.py',
            task['job_id']
        )

        script_path = os.path.join(
            "==jobpath==", "blender_opengl_render.py")

        output_path = os.path.join("==outputpath==", "####")

        task_command = [
        'DISPLAY=:0.0',
        str( blender_path ),
        '-noaudio',
        # note: not running in background here, because we need OpenGL
        #'--background',
        str( file_path ),
        '--python',
        str(script_path),
        '--enable-autoexec',
        '--', # arguments after this separator are used only by the script
        '--render-output',
        str(output_path),
        '--frame-start' ,
        str(settings['frame_start']),
        '--frame-end',
        str(settings['frame_end']),
        '--render-format',
        str(settings['format']),
        ]

        return task_command
