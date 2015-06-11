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
        template_path = os.path.join(dir, 'blender_bake_anim_cache.template')
        with open(template_path, "r") as f:
            script = f.read()
        f.close()

        add_file(
            script,
            'bake_anim_cache.py',
            task['job_id']
        )

        script_path = os.path.join(
            "==jobpath==", "bake_anim_cache.py")

        output_path = os.path.join("==outputpath==", "#####")

        task_command = [
        str( blender_path ),
        '-noaudio',
        '--background',
        str( file_path ),
        '--python',
        str(script_path),
        '--enable-autoexec'
        ]

        return task_command
