from flamenco.utils import frame_range_parse
from flamenco.utils import frame_range_merge


def compile_blender_simple_render(job, create_task):
    """The basic Blender render job."""
    job_settings = job['settings']
    parsed_frames = frame_range_parse(job_settings['frames'])
    chunk_size = job_settings['chunk_size']
    try:
        render_output = job_settings['render_output']
    except KeyError:
        render_output = None
    for i in range(0, len(parsed_frames), chunk_size):
        commands = []

        if not job_settings['filepath'].startswith('/'):
            cmd_download = {
                'name': 'download',
                'settings': {}
            }
            commands.append(cmd_download)

            cmd_unzip = {
                'name': 'unzip',
                'settings': {}
            }
            commands.append(cmd_unzip)

        frames = frame_range_merge(parsed_frames[i:i + chunk_size])
        cmd_render = {
            'name': 'blender_render',
            'settings': {
                'filepath': job_settings['filepath'],
                'format': job_settings['format'],
                'frames': frames
            }
        }
        if render_output:
            cmd_render['settings']['render_output'] = render_output

        commands.append(cmd_render)

        if not render_output:
            cmd_upload = {
                'name': 'upload',
                'settings': {}
            }
            commands.append(cmd_upload)

        create_task(job, commands, frames)
