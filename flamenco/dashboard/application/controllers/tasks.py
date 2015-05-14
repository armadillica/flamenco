import json
import os
import datetime

from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask import Blueprint
from flask import jsonify
from flask import make_response

from application import app
from application import http_server_request
from application.helpers import seconds_to_time

# Name of the Blueprint
tasks = Blueprint('tasks', __name__)


@tasks.route('/<int:task_id>.json')
def view_json(task_id):
    task = http_server_request('get', '/tasks/{0}'.format(task_id))
    # We check if we are asking to download the full log for the task
    is_log_download = request.args.get('log_dl')
    if is_log_download and task['log']:
        log = task['log']
        response = make_response(log)
        # Set the right header for the response to be downloaded, instead
        # of just printed on the browser
        filename_string = "attachment; filename=log_task_{0}.txt".format(task['id'])
        response.headers["Content-Disposition"] = filename_string
        return response

    elif task['log']:
        # If there is a log but we are not downloadig it, we trim it and append
        # the link to dowload the whole file
        log_trimmed = task['log'][-256:]
        log_trimmed = "{0} <a href=\"{1}\">Download</a>".format(log_trimmed, url_for('tasks.view_json', task_id=task['id'], log_dl=True))
        task['log'] = log_trimmed

    return jsonify(task)
