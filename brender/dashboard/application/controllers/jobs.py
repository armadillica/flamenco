import glob
import json
import os
import time
import urllib

from os import listdir
from os.path import isfile
from os.path import join
from os.path import abspath
from os.path import exists

from glob import iglob
from flask import flash
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask import send_file
from flask import make_response
from flask import Blueprint

from application import app
from application import list_integers_string
from application import http_server_request
# from server import RENDER_PATH

# TODO: find a better way to fill/use this variable
BRENDER_SERVER = app.config['BRENDER_SERVER']


# Name of the Blueprint
jobs = Blueprint('jobs', __name__)


@jobs.route('/')
def index():
    jobs = http_server_request('get', '/jobs')
    jobs_list = []

    for key, val in jobs.iteritems():

        #Settings
        settings_list = json.loads(val['settings'])
        settings= "<ul>"
        for setting in settings_list:
            settings="{0}<li><span style=\"font-weight:bold\">{1}</span>: {2}</li>".format(settings, setting, settings_list[setting])
        settings = "{0}</ul>".format(settings)

        #Tasks
        task_list = json.loads(val['tasks'])
        task_name = "<ul>"
        task_completion = "<ul>"
        task_activity = "<ul>"
        for task in task_list:
            task_name="{0}<li>{1}</li>".format(task_name, task['name'])
            task_completion="{0}<li>{1}</li>".format(task_completion, task['status'])
            task_activity="{0}<li>{1}</li>".format(task_activity, task['activity'])
        task_completion = "{0}</ul>".format(task_completion)
        task_activity = "{0}</ul>".format(task_activity)
        task_name = "{0}</ul>".format(task_name)

        val['checkbox'] = '<input type="checkbox" value="' + key + '" />'
        jobs_list.append({
            "DT_RowId": "job_" + str(key),
            "0": val['checkbox'],
            "1": key,
            "2": val['job_name'],
            "3": val['percentage_done'],
            "4": settings,
            "5": val['status'],
            "6" : 'http://%s/jobs/thumbnails/%s' % (BRENDER_SERVER, key),
            "7" : task_name,
            "8" : task_completion,
            "9" : task_activity,
            })
        #print(v)

    jobs_list = sorted(jobs_list, key=lambda x: x['1'])
    entries = json.dumps(jobs_list)

    return render_template('jobs/index.html', entries=entries, title='jobs')

@jobs.route('/<job_id>')
def job(job_id):
    print '[Debug] job_id is %s' % job_id
    job = http_server_request('get', '/jobs/' + job_id)
    #job['thumb'] = last_thumbnail(job['id'])
    # render_dir = RENDER_PATH + "/" + str(job['id']) +  '/'
    # if exists(render_dir):
    #     job['render'] = map(lambda s : join("/" + render_dir, s), \
    #                     filter(lambda s : s.endswith(".thumb"), listdir(render_dir)))
    # else:
    #     job['render'] = '#'

    return render_template('jobs/view.html', job=job)


@jobs.route('/browse/', defaults={'path': ''})
@jobs.route('/browse/<path:path>',)
def jobs_browse(path):
    if len(path) > 0:
        path = os.path.join('/browse', path)
    else:
        path = "/browse"
    print path
    path_data = http_server_request('get', path)
    return render_template('browse_modal.html',
        # items=path_data['items'],
        items_list=path_data['items_list'],
        parent_folder=path_data['parent_path'])


@jobs.route('/delete', methods=['POST'])
def jobs_delete():
    job_ids = request.form['id']
    print(job_ids)
    params = {'id': job_ids}
    jobs = http_server_request('post', '/jobs/delete', params)
    return 'done'


@jobs.route('/update', methods=['POST'])
def jobs_update():
    command = request.form['command'].lower()
    job_ids = request.form['id']
    params = {'id': job_ids,
              'status' : command}
    if command in ['start', 'stop', 'respawn', 'reset']:
        jobs = http_server_request('put',
            '/jobs', params)
        return 'done'
    else:
        return 'error', 400


@jobs.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        job_values = {
            'project_id': request.form['project_id'],
            'job_name': request.form['job_name'],
            'frame_start': request.form['frame_start'],
            'frame_end': request.form['frame_end'],
            'chunk_size': request.form['chunk_size'],
            'current_frame': request.form['frame_start'],
            'filepath': request.form['filepath'],
            'render_settings': request.form['render_settings'],
            'format' : request.form['format'],
            'status': 'stopped',
            'priority': 10,
            'managers' : request.form.getlist('managers'),
            'owner': 'fsiddi'
        }

        http_server_request('post', '/jobs', job_values)

        #  flashing does not work because we use redirect_url
        #  flash('New job added!')

        return redirect(url_for('jobs.index'))
    else:
        render_settings = http_server_request('get', '/settings/render')
        projects = http_server_request('get', '/projects')
        settings = http_server_request('get', '/settings')
        managers = http_server_request('get', '/managers')
        return render_template('jobs/add_modal.html',
                            render_settings=render_settings,
                            settings=settings,
                            projects=projects,
                            managers=filter(lambda m : m['connection'] == 'online',
                                            managers.values()))

