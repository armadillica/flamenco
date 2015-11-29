import os
import logging
import subprocess
import re
import json
try:
    from PIL import Image, ImageOps
except ImportError:
    #raise RuntimeError('Image module of PIL needs to be installed')
    logging.warning("Image module of PIL needs to be installed")

from application.config_base import Config
from common.blender_parser import *

class task_parser():
    @staticmethod
    def parse(output, options, activity):

        if activity:
            activity = json.loads(activity)
        settings = options['settings']

        if not activity:
            activity = {
                'process' : "",
                'remaining' : None,
                'thumbnail' : None,
                'current_frame' : None,
                'path_not_found': None,
                'unable_to_open': None,
            }

        unable_to_open = blender_parser.unable_to_open(output)
        if unable_to_open:
            activity['unable_to_open'] = unable_to_open

        path_not_found = blender_parser.path_not_found(output)
        if path_not_found:
            activity['path_not_found'] = path_not_found

        current_frame = blender_parser.current_frame(output)
        if current_frame:
            activity['current_frame'] = current_frame

        remaining = blender_parser.remaining(output)
        if remaining:
            #if current_frame:
            #    remaining=(settings['frame_end']-current_frame+1)*remaining
            activity['remaining'] = int(remaining)

        process = blender_parser.process(output)
        if process:
            activity['process'] = process

        saved_file = blender_parser.saved_file(output)

        if saved_file:
            file_name = "thumbnail_%s.png" % options['task_id']
            output_path = os.path.join(Config.STORAGE_DIR,
                                       file_name)
            print('Saving {0} to {1}'.format(file_name, output_path))
            tmberror = False
            try:
                im = Image.open(saved_file)
                im.save(output_path, 'PNG')
            except IOError, e:
                tmberror = True
                logging.error("PIP error reading or writing the Thumbnail: {0}".format(e))
            except NameError, e:
                tmberror = True
                logging.error("PIP lib not loaded: {0}".format(e))
            if tmberror:
                try:
                    tmberror = False
                    subprocess.call([
                        "convert", "-identify", saved_file,
                        "-set", "colorspace", "sRGB",
                        "-colorspace", "RGB",  output_path ])
                except:
                    tmberror = True
                    logging.error("Error running convert (Imagemagick)")
            if not tmberror:
                activity['thumbnail'] = output_path
        else:
            activity['thumbnail'] = None

        return json.dumps(activity)
