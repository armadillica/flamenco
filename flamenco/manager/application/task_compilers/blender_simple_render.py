import os
import json

def parse(s):
    all_frames = []
    for part in s.split(','):
        x = part.split("-")
        num_parts = len(x)
        if num_parts == 1:
            # Individual frame
            all_frames += ["-f", str(x[0])]
        elif num_parts == 2:
            # Frame range
            all_frames += ["--frame-start", str(x[0]), "--frame-end", str(x[1]), "--render-anim"]
    return all_frames

class task_compiler():
    @staticmethod
    def compile(worker, task, add_file):

        settings = task['settings']
        file_path = os.path.join('==jobpath==', settings['filepath'])
        output_path = "==outputpath=="
        blender_path = "==command=="

        dir = os.path.dirname(__file__)
        template_path = os.path.join(dir, 'blender_simple_render.template')
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

        output_path = os.path.join("==outputpath==", "#####")

        task_command = [
        str(blender_path),
        '--enable-autoexec',
        '-noaudio',
        '--background',
        str(file_path),
        '--render-output',
        str(output_path),
        '--python',
        str(script_path),
        '--render-format',
        str(settings['format'])] + parse(settings['frames'])

        return task_command
