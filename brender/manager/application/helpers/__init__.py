import os
import time
import requests
import logging
from hashlib import md5
from threading import Thread
from werkzeug import secure_filename
from flask import flash
from application import app


def http_request(ip_address, command, method, params=None):
    if method == 'delete':
        r = requests.delete('http://' + ip_address + command)
    elif method == 'post':
        r = requests.post('http://' + ip_address + command, data=params)
    elif method == 'get':
        r = requests.get('http://' + ip_address + command)
    elif method == 'put':
        r = requests.put('http://' + ip_address + command, data=params)
    elif method == 'patch':
        r = requests.patch('http://' + ip_address + command, data=params)

    if r.status_code == 404:
        return abort(404)

    # Only for debug
    if r.status_code == 400:
        for chunk in r.iter_content(50):
            print chunk
        return abort(404)

    if r.status_code == 204:
        return '', 204

    if r.status_code >= 500:
        logging.debug("STATUS CODE: %d" % r.status_code)
        return abort(500)

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
