from flamenco.utils import frame_range_parse
from flamenco.utils import frame_range_merge


def compile_sleep_simple(job, create_task):
    job_settings = job['settings']
    parsed_frames = frame_range_parse(job_settings['frames'])
    chunk_size = job_settings['chunk_size']
    # Loop to generate all tasks
    for i in range(0, len(parsed_frames), chunk_size):
        commands = []
        cmd_echo = {
            'name': 'echo',
            'settings': {
                'message': 'Preparing to sleep'
            }
        }
        commands.append(cmd_echo)
        cmd_sleep = {
            'name': 'sleep',
            'settings': {
                'time_in_seconds': job_settings['time_in_seconds'],
            }
        }
        commands.append(cmd_sleep)
        name = frame_range_merge(parsed_frames[i:i + chunk_size])
        create_task(job, commands, name)
