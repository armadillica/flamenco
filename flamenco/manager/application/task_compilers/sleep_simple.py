class TaskCompiler:
    def __init__(self):
        pass

    @staticmethod
    def compile(task, add_file=None, worker=None):
        """Build commands according to the OS. For the moment no OS is provided
        because we are not passing a worker, but we will.
        """
        commands = []
        # Compile echo
        cmd_echo = task['commands'][0]
        cmd_echo_dict = dict(
            name=cmd_echo['name'],
            command=[cmd_echo['name'], cmd_echo['settings']['message']])
        commands.append(cmd_echo_dict)

        # Compile sleep
        cmd_sleep = task['commands'][1]
        cmd_sleep_dict = dict(
            name=cmd_sleep['name'],
            command=[
                cmd_sleep['name'],
                str(cmd_sleep['settings']['time_in_seconds'])])
        commands.append(cmd_sleep_dict)
        return commands
