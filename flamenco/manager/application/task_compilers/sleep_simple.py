from application.modules.job_types import get_job_type_paths


class TaskCompiler:
    def __init__(self):
        pass

    @staticmethod
    def compile(task, add_file=None, worker=None):
        paths = get_job_type_paths('sleep_simple', worker)
        commands = []
        # Compile echo
        cmd_echo = task['commands'][0]
        cmd_echo_dict = dict(
            name=cmd_echo['name'],
            command=[cmd_echo['name'], cmd_echo['settings']['message']])
        commands.append(cmd_echo_dict)

        # Compile sleep
        cmd_sleep = task['commands'][1]
        # Get the name of the command for each OS (on Win is 'timeout')
        cmd_sleep['name'] = '{sleep}'.format(**paths)
        cmd_sleep_dict = dict(
            name=cmd_sleep['name'],
            command=[
                cmd_sleep['name'],
                str(cmd_sleep['settings']['time_in_seconds'])])
        commands.append(cmd_sleep_dict)
        return commands
