import glob
import json
import os
import time
from os import listdir
from os.path import isfile, join, abspath
from glob import iglob
from flask import flash
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask import make_response
from flask import Blueprint

from application import app
from application import http_server_request
from application import list_integers_string
from application import check_connection

from application.controllers.jobs import jobs


# Name of the Blueprint
main = Blueprint('main', __name__)

@main.route('/')
def index():
    if check_connection() == 'online':
        return redirect(url_for('jobs.index'))
    else:
        return "[error] Dashboard could not connect to server"

@main.route('/about')
def about():
        return render_template('about.html')

