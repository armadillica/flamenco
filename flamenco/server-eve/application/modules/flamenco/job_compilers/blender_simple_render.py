from application.modules.flamenco.utils import frame_range_parse
from application.modules.flamenco.utils import frame_range_merge


class JobCompiler:

    def __init__(self):
        pass

    @staticmethod
    def compile(job, create_task):
        """The basic Blender render job. We get a blenfile as input and return
        a frame sequence as output. The job is structured as follows.

        Input -> Render Job -> Output

        There are a few possible scenarios when creating this job:
        - we provide the .blend file from a shared location (NFS, SMB)
        - we upload the .blend file to the server
        Simlar logic is adopted for the output:
        - we save the render ouput on a shared location (NFS, SMB)
        - we upload the output to the server

        In the case where we upload and download data from the server, we need
        to provide storage access to the manager and mirror such storage setup
        on the manager in order to provide a layer of caching.

        The possible settings for the job type are:

        - filepath_output if specified, must be absolute and considered shared
        - filepath (string) if starts with / then is absolute
        - format
        - frames
        - chunk_size
        """
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
