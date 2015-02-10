import os
import subprocess
import re

from application import app

class blender_parser():

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
        r'Saved: (.*?)\s'
        )
        output_path = None
        match = re_frame.findall(output)
        if len(match):
            output_path=match[-1]
        return output_path
