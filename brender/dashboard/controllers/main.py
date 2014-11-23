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

from dashboard import app
from dashboard import http_request, list_integers_string, check_connection

from dashboard.controllers.workers import workers

# TODO: find a better way to fill/use this variable
BRENDER_SERVER = app.config['BRENDER_SERVER']

# Name of the Blueprint
main = Blueprint('main', __name__)

@main.route('/')
def index():
    if check_connection(BRENDER_SERVER) == 'online':
        return redirect(url_for('workers.index'))
    else:
        return "[error] Dashboard could not connect to server"


@main.route('/jobs/')
def jobs_index():
    jobs = http_request(BRENDER_SERVER, '/jobs')
    jobs_list = []

    for key, val in jobs.iteritems():
        val['checkbox'] = '<input type="checkbox" value="' + key + '" />'
        jobs_list.append({
            "DT_RowId": "worker_" + str(key),
            "0": val['checkbox'],
            "1": key,
            "2": val['percentage_done'],
            "3": val['priority'],
            "4": val['status']
            })
        #print(v)

    entries = json.dumps(jobs_list)

    return render_template('jobs.html', entries=entries, title='jobs')


@main.route('/log/', methods=['GET', 'POST'])
def log():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    onlyfiles = [f for f in listdir(path) if isfile(join(path, f))]
    log_files = []
    for i in glob.iglob('*.log'):
        log_files.append(i)
    print('[Debug] %s') % log_files
    if request.method == 'POST':

        result = request.form['log_files']
        if result:
            try:
                with open(result) as log:
                        lines = log.readlines()
                return render_template('log.html',
                                       title='logs',
                                       lines=lines,
                                       result=result,
                                       log_files=log_files)
            except IOError:
                flash('Couldn\'t open file. ' +
                      'Please make sure the log file exists at ' + result)
        else:
            flash('No log to read Please input a filepath ex: ' +
                  'log.log')
    return render_template('log.html', title='logs', log_files=log_files)


@main.route('/sandbox/')
def sandbox():
    return render_template('sandbox.html', title='sandbox')

