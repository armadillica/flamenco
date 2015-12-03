import re
import urllib
import requests
import logging
from flask import abort


class FlamencoManager(object):
    """Basic Flamenco Manager client"""
    def __init__(self, manager_endpoint):
        """Initialize the Manager client.

        :param manager_endpoint: the full url to reach the manager, for example
            ("http://manager:7777")
        :type manager_endpoint: string
        """
        self.manager_endpoint = manager_endpoint

    def parse_result(self, r):
        """Process the response object that comes from the request and in case
        of success, return it as JSON.
        """
        if r.status_code >= 500:
            logging.error("STATUS CODE: %d" % r.status_code)
            return '', 500
        if r.status_code == 404:
            return '', 404
        elif r.status_code == 204:
            return '', 204
        else:
            return r.json()

    def get(self, resource):
        """Create a GET request"""
        r = requests.get(join_url(self.manager_endpoint, resource))
        return self.parse_result(r)


def http_request(ip_address, command, post_params=None):
    # post_params must be a dictionay
    if post_params:
        params = urllib.urlencode(post_params)
        f = urllib.urlopen('http://' + ip_address + command, params)
    else:
        f = urllib.urlopen('http://' + ip_address + command)

    print('message sent, reply follows:')
    print(f.read())

def http_rest_request(ip_address, command, method, params=None, files=None):
    if method == 'delete':
        r = requests.delete('http://' + ip_address + command, data=params)
    elif method == 'post':
        r = requests.post('http://' + ip_address + command, data=params, files=files)
    elif method == 'get':
        r = requests.get('http://' + ip_address + command)
    elif method == 'put':
        r = requests.put('http://' + ip_address + command, data=params)
    elif method == 'patch':
        r = requests.patch('http://' + ip_address + command, data=params)

    if r.status_code == 404:
        return '', 404

    if r.status_code == 204:
        return '', 204

    return r.json()

# That seems totally useless but keep it
# in case of future bugs due to system path separator
#from platform import system
#def system_path(path):
#    if system() is "Windows":
#        return path.replace('/', '\\')
#    return path

def list_integers_string(string_list):
    """
    Accepts comma separated string list of integers
    """
    integers_list = string_list.split(',')
    integers_list = map(int, integers_list)
    return integers_list

def get_file_ext(string):
    if string == "MULTILAYER":
        return ".exr"
    if string == 'JPEG':
        return ".jpg"
    return "." + string.lower()


def frame_percentage(item):
    if item.frame_start == item.current_frame:
            return 0
    else:
        frame_count = item.frame_end - item.frame_start + 1
        current_frame = item.current_frame - item.frame_start + 1
        percentage_done = 100 / frame_count * current_frame
        return percentage_done


def pretty_date(time=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    from datetime import datetime
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time,datetime):
        diff = now - time
    elif not time:
        diff = now - now
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + " seconds ago"
        if second_diff < 120:
            return  "a minute ago"
        if second_diff < 3600:
            return str( second_diff / 60 ) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str( second_diff / 3600 ) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff <= 7:
        return str(day_diff) + " days ago"
    if day_diff <= 31:
        week_count = day_diff/7
        if week_count == 1:
            return str(week_count) + " week ago"
        else:
            return str(week_count) + " weeks ago"
    if day_diff <= 365:
        return str(day_diff/30) + " months ago"
    return str(day_diff/365) + " years ago"


def frame_range_parse(frame_range=None):
    """Given a range of frames, return a list containing each frame.

    :Example:

    >>> frames = "1,3-5,8"
    >>> frame_range_parse(frames)
    >>> [1, 3, 4, 5, 8]

    """
    if not frame_range:
        return list()

    frames_list = []
    for part in frame_range.split(','):
        x = part.split("-")
        num_parts = len(x)
        if num_parts == 1:
            frame = int(x[0])
            frames_list.append(frame)
            #print("Individual frame %d" % (frame))
        elif num_parts == 2:
            frame_start = int(x[0])
            frame_end = int(x[1])
            frames_list += range(frame_start, frame_end + 1)
            #print("Frame range %d-%d" % (frame_start, frame_end))
    frames_list.sort()
    return frames_list



def frame_range_merge(frames_list=None):
    """Given a frames list, merge them and return them as range of frames.

    :Example:

    >>> frames = [1, 3, 4, 5, 8]
    >>> frame_range_merge(frames)
    >>> "1,3-5,8"

    """
    if not frames_list:
        return ""
    ranges = []
    current_frame = start_frame = prev_frame = frames_list[0]
    n = len(frames_list)
    for i in range(1, n):
        current_frame = frames_list[i]
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


def join_url(url, *paths):
    """Joins individual URL strings together, and returns a single string.

    Usage::

        >>> utils.join_url("flamenco:9999", "jobs")
        flamenco:9999/jobs
    """
    for path in paths:
        url = re.sub(r'/?$', re.sub(r'^/?', '/', path), url)
    return url

