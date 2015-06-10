import os

class task_compiler():
    @staticmethod
    def compile(worker, task, add_file):

        settings = task['settings']

        file_path = os.path.join('==jobpath==', settings['filepath'])
        output_path = "==outputpath=="

        blender_path = "==command=="

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
        str(blender_path),
        '-noaudio',
        '--background',
        str(file_path),
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
