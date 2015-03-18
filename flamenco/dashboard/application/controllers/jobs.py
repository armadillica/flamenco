import json
import os
import datetime

from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask import Blueprint
from flask import jsonify

from application import app
from application import http_server_request
from application.helpers import seconds_to_time

# TODO: find a better way to fill/use this variable
BRENDER_SERVER = app.config['BRENDER_SERVER']


# Name of the Blueprint
jobs = Blueprint('jobs', __name__)


@jobs.route('/')
def index():
    jobs = http_server_request('get', '/jobs')
    jobs_list = []

    for key, val in jobs.iteritems():

        remaining_time = val['remaining_time']
        if not remaining_time:
            remaining_time = '-'
        else:
            remaining_time = seconds_to_time(remaining_time)
        average_time = val['average_time']
        if not average_time:
            average_time = '-'
        else:
            average_time = seconds_to_time(average_time)
        total_time = val['total_time']
        if not total_time:
            total_time = '-'
        else:
            total_time = seconds_to_time(total_time)
        job_time = val['job_time']
        if job_time:
            total_time = "{0} ({1})".format(total_time, seconds_to_time(job_time))

        val['checkbox'] = '<input type="checkbox" value="' + key + '" />'
        jobs_list.append({
            "DT_RowId" : "job_" + str(key),
            "0" : val['checkbox'],
            "1" : key,
            "2" : 'http://{0}/jobs/thumbnails/{1}s'.format(BRENDER_SERVER, key),
            "3" : val['job_name'],
            "4" : val['percentage_done'],
            "5" : remaining_time,
            "6" : average_time,
            "7" : total_time,
            "8" : val['activity'],
            "9" : val['status'],
            "10" : None,
            "11" : val['creation_date']
            })

    jobs_list = sorted(jobs_list, key=lambda x: x['1'])
    entries = json.dumps(jobs_list)

    return render_template('jobs/index.html', entries=entries, title='jobs')

@jobs.route('/<int:job_id>')
def job(job_id):
    print '[Debug] job_id is %s' % job_id
    job = http_server_request('get', '/jobs/{0}'.format(job_id))
    job['settings'] = job['settings']

    #Tasks
    job['thumbnail'] = 'http://%s/jobs/thumbnails/%s' % (BRENDER_SERVER, job_id)
    return render_template('jobs/view.html', job=job)


@jobs.route('/<int:job_id>.json')
def view_json(job_id):
    """Light info to be retrieved via AJAX"""
    job = http_server_request('get', '/jobs/{0}'.format(job_id))
    job['total_time'] = seconds_to_time(job['total_time'])
    job['average_time'] = seconds_to_time(job['average_time'])
    return jsonify(job)


@jobs.route('/browse/', defaults={'path': ''})
@jobs.route('/browse/<path:path>',)
def jobs_browse(path):
    if len(path) > 0:
        path = os.path.join('/browse', path)
    else:
        path = "/browse"
    path_data = http_server_request('get', path)
    path_data_sorted = sorted(path_data['items_list'], key=lambda p: p[0])
    return render_template('browse_modal.html',
        # items=path_data['items'],
        items_list=path_data_sorted,
        parent_folder=path_data['parent_path'])


@jobs.route('/delete', methods=['POST'])
def jobs_delete():
    job_ids = request.form['id']
    params = {'id': job_ids}
    jobs = http_server_request('post', '/jobs/delete', params)
    return 'done'


@jobs.route('/update', methods=['POST'])
def jobs_update():
    command = request.form['command'].lower()
    job_ids = request.form['id']
    params = {'id': job_ids,
              'command' : command}
    if command in ['start', 'stop', 'respawn', 'reset']:
        jobs = http_server_request('put',
            '/jobs', params)
        return jsonify(jobs)
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
            'job_type' : request.form['job_type'],
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

