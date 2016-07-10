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
        command = "==command=="

        task_command = [
            str(command),
            str(settings['time_in_seconds'])]

        return task_command
