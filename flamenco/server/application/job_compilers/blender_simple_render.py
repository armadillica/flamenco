import os
import json
import logging

def parse(s):
    all_frames = []
    for part in s.split(','):
        x = part.split("-")
        num_parts = len(x)
        if num_parts == 1:
            frame = int(x[0])
            all_frames.append(frame)
            #print("Individual frame %d" % (frame))
        elif num_parts == 2:
            frame_start = int(x[0])
            frame_end = int(x[1])
            all_frames += range(frame_start, frame_end + 1)
            #print("Frame range %d-%d" % (frame_start, frame_end))

    #print(all_frames)
    all_frames.sort()
    return all_frames


def merge(all_frames):
    ranges = []
    current_frame = start_frame = prev_frame = all_frames[0]
    n = len(all_frames)
    for i in range(1, n):
        current_frame = all_frames[i]
        if current_frame == prev_frame + 1:
            pass
        else:
            if start_frame == prev_frame:
                ranges.append(str(start_frame))
            else:
                ranges.append("{0}-{1}".format(start_frame, prev_frame))
            start_frame = current_frame
        prev_frame = current_frame
    if start_frame == current_frame:
        ranges.append(str(start_frame))
    else:
        ranges.append("{0}-{1}".format(start_frame, current_frame))
    return ",".join(ranges)


class job_compiler():

    @staticmethod
    def compile(job, project, create_task):
        job_settings = json.loads(job.settings)
        task_type = 'blender_simple_render'
        parser = 'blender_render'

        task_settings = {}
        task_settings['filepath'] = job_settings['filepath']
        task_settings['priority'] = job.priority
        task_settings['render_settings'] = job_settings['render_settings']
        task_settings['format'] = job_settings['format']
        task_settings['command_name'] = job_settings['command_name']

        task_settings['file_path_linux'] = ""
        task_settings['file_path_win'] = ""
        task_settings['file_path_osx'] = ""

        task_settings['output_path_linux'] = '#####'
        task_settings['output_path_win'] = '#####'
        task_settings['output_path_osx'] = '#####'


        parsed_frames = parse(job_settings['frames'])
        chunk_size = job_settings['chunk_size']

        for i in xrange(0, len(parsed_frames), chunk_size):
            task_settings['frames'] = merge(parsed_frames[i:i + chunk_size])
            name = task_settings['frames']
            create_task(job.id, task_type, task_settings, name, None, parser)
