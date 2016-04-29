import os
import subprocess
import re


class blender_parser():
    @staticmethod
    def unable_to_open(output):
        # Check if blender is unable to open blendfile
        # Warning: Unable to open
        re_path = re.compile(
            r"Warning: Unable to open"
        )
        unable_to_open = False
        match = re_path.findall(output)
        if len(match):
            unable_to_open = True
        return unable_to_open

    @staticmethod
    def path_not_found(output):
        #Get missing paths
        # Warning: Path 'path' not found
        re_path = re.compile(
            r"Warning: Path '.*' not found"
        )
        not_found = False
        match = re_path.findall(output)
        if len(match):
            not_found = True
        return not_found

    @staticmethod
    def current_frame(output):
        #Get Activity
        # | Activity
        re_frame = re.compile(
        r'Fra:(\d*)'
        )
        current_frame=None
        match = re_frame.findall(output)
        if len(match):
            current_frame=int(match[-1])
        return current_frame

    @staticmethod
    def remaining(output):
        #Get Remaining
        #Remaining:[00:]00:00.01
        re_frame = re.compile(
        r'.* Remaining:(\d*):*(\d+):(\d+)\.(\d+)'
        )
        remaining=None
        match = re_frame.findall(output)
        if len(match):
            remaining=(int(match[-1][0])*60*60)+(int(match[-1][1])*60)+int(match[-1][2])
        return remaining

    @staticmethod
    def process(output):
        #Get Activity
        # | Activity
        re_frame = re.compile(
        r'.* \| (.*)'
        )
        process=None
        match = re_frame.findall(output)
        if len(match):
            if match[-1]!='Finished':
                process=match[-1]
        return process

    @staticmethod
    def saved_file(output):
        #Send Thumbnail
        #Saved: path
        re_frame = re.compile(
        r'Saved: \'(.*?)\'\s'
        )
        output_path = None
        match = re_frame.findall(output)
        if len(match):
            output_path=match[-1]
        return output_path
