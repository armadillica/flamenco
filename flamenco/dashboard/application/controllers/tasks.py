import json
import os
import datetime

from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask import Blueprint
from flask import jsonify
from flask import Response

from application import app
from application import http_server_request
from application.helpers import seconds_to_time

# Name of the Blueprint
tasks = Blueprint('tasks', __name__)


@tasks.route('/<int:task_id>.json')
def view_json(task_id):
    task = http_server_request('get', '/tasks/{0}'.format(task_id))
    # task['total_time'] = seconds_to_time(task['total_time'])
    # task['average_time'] = seconds_to_time(task['average_time'])
    # for task in task['tasks']:
    #     task['log'] = None
    return jsonify(task)


