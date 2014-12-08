import glob
import json
import os
import time
import urllib
from os import listdir
from os.path import isfile, join, abspath, exists
from glob import iglob
from flask import (flash,
                   Flask,
                   jsonify,
                   redirect,
                   render_template,
                   request,
                   url_for,
                   send_file,
                   make_response,
                   Blueprint)

from dashboard import app
from dashboard import http_request, list_integers_string
from dashboard import http_server_request
#from server import RENDER_PATH

# TODO: find a better way to fill/use this variable
BRENDER_SERVER = app.config['BRENDER_SERVER']


# Name of the Blueprint
jobs = Blueprint('jobs', __name__)

# def last_thumbnail(job_id):
#     render_dir = RENDER_PATH + "/" + str(job_id)
#     if not exists(render_dir):
#         return ""

#     files = sorted(["/" + render_dir + "/" + f for f in listdir(render_dir) if  f.endswith(".thumb")])
#     return files.pop() if files else ""


@jobs.route('/')
def index():
    jobs = http_server_request('get', '/jobs')
    jobs_list = []

    for key, val in jobs.iteritems():
        val['checkbox'] = '<input type="checkbox" value="' + key + '" />'
        jobs_list.append({
            "DT_RowId": "job_" + str(key),
            "0": val['checkbox'],
            "1": key,
            "2": val['job_name'],
            "3": val['percentage_done'],
            "4": val['render_settings'],
            "5": val['status'],
            "6" : last_thumbnail(key)})
        #print(v)

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
    path = os.path.join('/jobs/browse/', path)
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
    jobs = http_server_request('delete', '/jobs', params)
    return 'done'


@jobs.route('/update', methods=['POST'])
def jobs_update():
    command = request.form['command'].lower()
    job_ids = request.form['id']
    params = {'id': job_ids,
              'status' : command}
    if command in ['start', 'stop', 'reset']:
        jobs = http_server_request('put',
            '/jobs', params)
        return 'done'
    else:
        return 'error'


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
            'status': 'running',
            'priority': 10,
            'owner': 'fsiddi'
        }

        http_server_request('post', '/jobs', job_values)

        #  flashing does not work because we use redirect_url
        #  flash('New job added!')

        return redirect(url_for('jobs.index'))
    else:
        render_settings = http_request(BRENDER_SERVER, '/settings/render')
        projects = http_server_request('get', '/projects')
        settings = http_server_request('get', '/settings/')
        return render_template('jobs/add_modal.html',
                            render_settings=render_settings,
                            settings=settings,
                            projects=projects)

