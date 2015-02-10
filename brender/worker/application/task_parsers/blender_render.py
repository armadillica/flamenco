import os
import subprocess
import re
import json

from application import app
from common.blender_parser import *

class task_parser():
    @staticmethod
    def parse(output, options, activity):

    	if activity:
    		activity=json.loads(activity)
        settings=json.loads(options['settings'])

        if not activity:
            activity={
	            'process' : "",
	            'remaining' : None,
	            'thumbnail' : None,
	            'current_frame' : None,}

        current_frame=blender_parser.current_frame(output)
        if current_frame:
            activity['current_frame']=current_frame

        remaining=blender_parser.remaining(output)
        if remaining:
            #if current_frame:
            #    remaining=(settings['frame_end']-current_frame+1)*remaining
            activity['remaining']=int(remaining)

        process=blender_parser.process(output)
        if process:
            activity['process']=process

        saved_file=blender_parser.saved_file(output)
        if saved_file:
            file_name = "thumbnail_%s.png" % options['task_id']
            output_path = os.path.join(app.config['TMP_FOLDER'], file_name)
            subprocess.call(["convert", "-identify", saved_file, "-colorspace", "RGB", output_path ])
            activity['thumbnail']=output_path
        else:
        	activity['thumbnail']=None

        return json.dumps(activity)