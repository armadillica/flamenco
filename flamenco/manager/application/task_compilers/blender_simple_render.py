from application.helpers import parse
from application.modules.job_types import get_job_type_paths


class TaskCompiler:
    def __init__(self):
        pass

    @staticmethod
    def compile(task, add_file=None, worker=None):

        paths = get_job_type_paths('blender_simple_render', worker)

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

            # Check if a command has been defined, or use the default definition.
            try:
                blender_cmd = cmd_settings['blender_cmd']
            except KeyError:
                blender_cmd = '{blender_render}'
            # Do path remapping
            blender_cmd = blender_cmd.format(**paths)

            # Parse the file path. This property is required, so we crash if not set.
            filepath = cmd_settings['filepath']
            # Do path remapping
            filepath = filepath.format(**paths)

            # Look for render_output. If not specified we use what's in the file,
            # assuming it is an absolute path.
            try:
                render_output = cmd_settings['render_output']
                # Do path remapping
                render_output = render_output.format(**paths)

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
