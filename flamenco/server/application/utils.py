import urllib
import requests
from flask import abort


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
