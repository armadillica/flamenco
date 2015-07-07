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

# TODO: find a better way to fill/use this variable
FLAMENCO_SERVER = app.config['FLAMENCO_SERVER']


# Name of the Blueprint
jobs = Blueprint('jobs', __name__)


@jobs.route('/')
def index():
    return render_template('jobs/index.html', title='jobs')


@jobs.route('/index.json')
def index_json():
    """Generate DataTable-ready JSON with all non archived jobs. Accepts a 'pretty'
    argument that will pretty print the list.
    """

    # Check if we are requesting for a specific status (e.g. archived)
    if request.args.get('status'):
        jobs_route = "/jobs?status={0}".format(request.args.get('status'))
    else:
        jobs_route = '/jobs'

    jobs = http_server_request('get', jobs_route)
    jobs_list = []

    for key, val in jobs.iteritems():

        remaining_time = val['time_remaining']
        if not remaining_time:
            remaining_time = '-'
        else:
            remaining_time = seconds_to_time(remaining_time)
        average_time = val['time_average']
        if not average_time:
            average_time = '-'
        else:
            average_time = seconds_to_time(average_time)
        total_time = val['time_total']
        if not total_time:
            total_time = '-'
        else:
            total_time = seconds_to_time(total_time)
        job_time = None
        if job_time:
            total_time = "{0} ({1})".format(total_time, seconds_to_time(job_time))

        time_elapsed = val['time_elapsed']
        if time_elapsed == None:
            time_elapsed = ''
        else:
            time_elapsed = seconds_to_time(time_elapsed)

        val['checkbox'] = '<input type="checkbox" value="' + key + '" />'
        jobs_list.append({
            'DT_RowId' : 'job_' + str(key),
            'checkbox' : val['checkbox'],
            'job_id' : key,
            'thumbnail' : 'http://{0}/jobs/thumbnails/{1}s'.format(FLAMENCO_SERVER, key),
            'name' : val['job_name'],
            'percentage_done' : val['percentage_done'],
            'time_remaining' : remaining_time,
            'time_average' : average_time,
            'time_total' : total_time,
            'status' : val['status'],
            'date_creation' : val['creation_date'],
            'date_edit' : val['date_edit'],
            'priority' : val['priority'],
            'manager': val['manager'],
            'time_elapsed': time_elapsed,
            'tasks_status': val['tasks_status'],
            'username': val['username']
            })

    #jobs_list = sorted(jobs_list, key=lambda x: x['1'])

    # For debugging, if we add the pretty arg to the get request, we get a pretty
    # printed version of the jobs_list
    if request.args.get('pretty'):
        if request.args.get('pretty') == 'true':
            return jsonify(data=jobs_list)


    # Default json return
    jobs_list_dict = {'data': jobs_list}
    content = u"{0}".format(json.dumps(jobs_list_dict))
    return Response(content, mimetype='application/json')


@jobs.route('/<int:job_id>')
def job(job_id):
    job = http_server_request('get', '/jobs/{0}'.format(job_id))
    #Tasks
    job['thumbnail'] = 'http://%s/jobs/thumbnails/%s' % (FLAMENCO_SERVER, job_id)
    return render_template('jobs/view.html', job=job)


@jobs.route('/<int:job_id>.json')
def view_json(job_id):
    """Light info to be retrieved via AJAX"""
    job = http_server_request('get', '/jobs/{0}'.format(job_id))
    job['total_time'] = seconds_to_time(job['total_time'])
    job['average_time'] = seconds_to_time(job['average_time'])
    job['average_time_frame'] = seconds_to_time(job['average_time_frame'])
    job['thumbnail'] = 'http://%s/jobs/thumbnails/%s' % (FLAMENCO_SERVER, job_id)
    for task in job['tasks']:
        task['log'] = None
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
    if command in ['start', 'stop', 'respawn', 'reset', 'archive']:
        jobs = http_server_request('put',
            '/jobs', params)
        return jsonify(jobs)
    else:
        return 'error', 400

@jobs.route('/<int:job_id>/edit', methods=['POST'])
def edit(job_id):

    params = {}
    for f in  request.form:
        params[f] = request.form[f]

    job = http_server_request('put', '/jobs/{0}'.format(job_id), params)
    return jsonify(job)


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
            'status': 'waiting',
            'priority': 10,
            'managers' : request.form.getlist('managers'),
            'job_type' : request.form['job_type'],
            'owner': 'fsiddi'
        }

        http_server_request('post', '/jobs', job_values)
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

