import os


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


class TaskCompiler:
    def __init__(self):
        pass

    @staticmethod
    def compile(task, add_file=None, worker=None):

        def _compile_download(cmd_settings):
            pass

        def _compile_unzip(cmd_settings):
            pass

        def _compile_blender_render(cmd_settings):
            """Build the blender render command. Strings that are checked for remapping are:
            - blender_cmd
            - filepath
            - render_output
            """
            # Get path remapping for the current job_type
            remaps_for_os = {
                'blender_render': '/Applications/Blender/buildbot/blender.app/Contents/MacOS/blender',
                'shared': '/shared',
                'something': '/something'
            }

            # Check if a render command has been defined. If not, use the default definition.
            try:
                blender_cmd = cmd_settings['blender_cmd']
            except KeyError:
                blender_cmd = '{blender_render}'
            # Do path remapping
            blender_cmd = blender_cmd.format(**remaps_for_os)

            # Parse the filepath. This property is required, so we will crash if not set.
            filepath = cmd_settings['filepath']
            # Do path remapping
            filepath = filepath.format(**remaps_for_os)

            # Look for render_output. If not specified we use what's in the file, assuming it is an
            # absolute path.
            try:
                render_output = cmd_settings['render_output']
                # Do path remapping
                render_output = render_output.format(**remaps_for_os)

            except KeyError:
                render_output = None

            cmd = [
                blender_cmd,
                '--enable-autoexec',
                '-noaudio',
                '--background',
                filepath]
            if render_output:
                cmd += [
                    '--render-output',
                    render_output
                ]
            cmd += [
                '--render-format',
                cmd_settings['format']
            ]
            # TODO: handle --python script path
            cmd += parse(cmd_settings['frames'])
            return cmd

        def _compile_upload(cmd_settings):
            pass

        command_map = {
            'download': _compile_download,
            'unzip': _compile_unzip,
            'blender_render': _compile_blender_render,
            'upload': _compile_upload
        }

        commands = []

        for command in task['commands']:
            cmd_dict = dict(
                name=command['name'],
                command=command_map[command['name']](command['settings'])
            )
            commands.append(cmd_dict)

        return commands

        # dir = os.path.dirname(__file__)
        # template_path = os.path.join(dir, 'blender_simple_render.template')
        # with open(template_path, "r") as f:
        #     script = f.read()
        # f.close()
        #
        # add_file(
        #     script,
        #     'pre_render.py',
        #     task['job']
        # )
        #
        # script_path = os.path.join(
        #     "==jobpath==", "pre_render.py")

