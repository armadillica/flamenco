import os
import time
import requests
import logging
import re

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

from threading import Thread
from pillarsdk import Api
from application import app

def http_request(ip_address, command, method, params=None, files=None):
    if method == 'delete':
        r = requests.delete('http://' + ip_address + command)
    elif method == 'post':
        r = requests.post('http://' + ip_address + command, data=params, files=files)
    elif method == 'get':
        r = requests.get('http://' + ip_address + command)
    elif method == 'put':
        r = requests.put('http://' + ip_address + command, data=params, files=files)
    elif method == 'patch':
        r = requests.patch('http://' + ip_address + command, data=params)

    if r.status_code == 404:
        return '', 404

    # Only for debug
    if r.status_code == 400:
        for chunk in r.iter_content(50):
            print chunk
        return '', 404

    if r.status_code == 204:
        return '', 204

    if r.status_code >= 500:
        logging.debug("STATUS CODE: %d" % r.status_code)
        return '', 500

    return r.json()


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


def async(f):
    """Use this as a decorator for asyncronous operations
    """
    def wrapper(*args, **kwargs):
        thr = Thread(target = f, args = args, kwargs = kwargs)
        thr.start()
    return wrapper


def join_url(url, *paths):
    """Joins individual URL strings together, and returns a single string.

    Usage::

        >>> utils.join_url("flamenco:9999", "jobs")
        flamenco:9999/jobs
    """
    for path in paths:
        url = re.sub(r'/?$', re.sub(r'^/?', '/', path), url)
    return url


def join_url_params(url, params):
    """Constructs a query string from a dictionary and appends it to a url.

    Usage::

        >>> utils.join_url_params("flamenco:9999/jobs", {"id": 2, "job_type": "render"})
        flamenco:9999/jobs?d=2&job_type=render
    """
    return url + "?" + urlencode(params)


def merge_dict(data, *override):
    """
    Merges any number of dictionaries together, and returns a single dictionary.

    Usage::

        >>> utils.merge_dict({"foo": "bar"}, {1: 2}, {"foo1": "bar2"})
        {1: 2, 'foo': 'bar', 'foo1': 'bar2'}
    """
    result = {}
    for current_dict in (data,) + override:
        result.update(current_dict)
    return result


def get_flamenco_server_api_object():
    """Temp utility to get an API object to be used"""
    return Api(
        endpoint=app.config['FLAMENCO_SERVER'],
        username=None,
        password=None,
        token=app.config['FLAMENCO_SERVER_TOKEN']
    )


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
            all_frames += ["--frame-start", str(x[0]), "--frame-end", str(x[1]),
                           "--render-anim"]
    return all_frames
