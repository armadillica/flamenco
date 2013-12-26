import glob
import json
import os
import time
import urllib
from os import listdir
from os.path import isfile, join, abspath
from glob import iglob

from flask import (flash,
                   Flask,
                   jsonify,
                   redirect,
                   render_template,
                   request,
                   url_for,
                   make_response)

BRENDER_SERVER = 'brender-server:9999'

app = Flask(__name__)
app.config.update(
    DEBUG=True,
    SERVER_NAME='brender-flask:8888'
)


def http_request(ip_address, method, post_params=False):
    # post_params must be a dictionnary
    if post_params:
        params = urllib.urlencode(post_params)
        f = urllib.urlopen('http://' + ip_address + method, params)
    else:
        f = urllib.urlopen('http://' + ip_address + method)

    print('message sent, reply follows:')
    return f.read()

def list_integers_string(string_list):
    """Accepts comma separated string list of integers
    """
    integers_list = string_list.split(',')
    integers_list = map(int, integers_list)
    return integers_list


@app.route('/')
def index():
    if check_connection(BRENDER_SERVER) == 'online':
        return redirect(url_for('workers'))
    else:
        return "[error] Dashboard could not connect to server"


@app.route('/workers/')
def workers():
    workers = http_request(BRENDER_SERVER, '/workers')
    #print(workers)
    workers = json.loads(workers)
    workers_list = []

    for key, val in workers.iteritems():
        val['checkbox'] = '<input type="checkbox" value="' + str(val['id']) + '"/>'
        workers_list.append({
            "DT_RowId": "worker_" + str(val['id']),
            "0": val['checkbox'],
            "1": key,
            "2": val['system'],
            "3": val['ip_address'],
            "4": val['connection'],
            "5": val['status']
        })
        #print(v)

    entries = json.dumps(workers_list)

    return render_template('workers.html', entries=entries, title='workers')



@app.route('/workers/edit', methods=['POST'])
def workers_edit():
    worker_ids = request.form['id']
    worker_status = request.form['status'].lower()

    worker_config = {'system': 'linux',
                     'blender': 'local'}
    params = urllib.urlencode({'id': worker_ids,
                               'status': worker_status,
                               'config': worker_config})
    f = urllib.urlopen("http://" + BRENDER_SERVER + "/workers/edit", params)

    return jsonify(status='ok')


@app.route('/worker/<worker_id>')
def worker(worker_id):
    #print(workers)
    worker = None
    try:
        workers = http_request(BRENDER_SERVER, '/workers')
        workers = json.loads(workers)
    except KeyError:
        '''
            there are multiple exceptions that we can use here

            1. KeyError
            2. UnboundLocalError
            3. NameError
            '''
        print 'worker does not exist'

    if worker_id in workers:
        for key, val in workers.iteritems():
            if worker_id in key:
                try:
                    worker = http_request(val['ip_address'], '/run_info')
                    worker = json.loads(worker)
                    entry = ({"ip_address": val['ip_address'], "worker_id": worker_id, "status": val['status']})
                    worker.update(entry)
                except IOError:
                    worker = {
                        'worker_id': worker_id,
                        'status': val['status'],
                        'update_frequent': {
                            'load_average': {
                                '5min': 'N/A',
                                '1min': 'N/A',
                                '15min': 'N/A'
                            },
                            'worker_num_cpus': 'N/A',
                            'worker_cpu_percent': 'N/A',
                            'worker_architecture': 'N/A',
                            'worker_mem_percent': 'N/A',
                            'worker_disk_percent': 'N/A'
                        },
                        'hostname': 'N/A',
                        'system': 'N/A',
                        'mac_address': 'N/A',
                        'worker_blender_cpu_usage': 'N/A',
                        'worker_blender_mem_usage': 'N/A'
                    }

    if worker:
        return render_template('worker.html', worker=worker)
    else:
        return make_response('worker ' + worker_id + ' doesnt exist')


@app.route('/shows/')
def shows_index():
    shows = http_request(BRENDER_SERVER, '/shows')
    shows= json.loads(shows)
    return render_template('shows.html', shows=shows, title='shows')


@app.route('/shows/update', methods=['POST'])
def shows_update():

    params = dict(
        show_id=request.form['show_id'],
        path_server=request.form['path_server'],
        path_linux=request.form['path_linux'],
        path_osx=request.form['path_osx'])

    print http_request(BRENDER_SERVER, '/shows/update', params)

    shows = http_request(BRENDER_SERVER, '/shows/')
    shows = json.loads(shows)
    return render_template('shows.html', shows=shows, title='shows')


@app.route('/shots/')
def shots_index():
    shots = http_request(BRENDER_SERVER, '/shots')
    #print(shots)
    shots = json.loads(shots)
    shots_list = []

    for key, val in shots.iteritems():
        val['checkbox'] = '<input type="checkbox" value="' + key + '" />'
        shots_list.append({
            "DT_RowId": "shot_" + str(key),
            "0": val['checkbox'],
            "1": key,
            "2": val['shot_name'],
            "3": val['percentage_done'],
            "4": val['render_settings'],
            "5": val['status']})
        #print(v)

    entries = json.dumps(shots_list)

    return render_template('shots.html', entries=entries, title='shots')


@app.route('/shots/browse/', defaults={'path': ''})
@app.route('/shots/browse/<path:path>',)
def shots_browse(path):
    path = os.path.join('/shots/browse/', path)
    print path
    path_data = json.loads(http_request(BRENDER_SERVER, path))
    return render_template('browse_modal.html',
        # items=path_data['items'],
        items_list=path_data['items_list'],
        parent_folder=path + '/..')


@app.route('/shots/delete', methods=['POST'])
def shots_delete():
    shot_ids = request.form['id']
    print(shot_ids)
    params = {'id': shot_ids}
    shots = http_request(BRENDER_SERVER, '/shots/delete', params)
    return 'done'


@app.route('/shots/update', methods=['POST'])
def shots_start():
    command = request.form['command'].lower()
    shot_ids = request.form['id']
    params = {'id': shot_ids}
    if command in ['start', 'stop', 'reset']:
        shots = http_request(BRENDER_SERVER,
            '/shots/%s' % (command), params)
        return shots
    else:
        return 'error'


@app.route('/shots/add', methods=['GET', 'POST'])
def shots_add():
    if request.method == 'POST':
        shot_values = {
            'attract_shot_id': 1,
            'show_id': request.form['show_id'],
            'shot_name': request.form['shot_name'],
            'frame_start': request.form['frame_start'],
            'frame_end': request.form['frame_end'],
            'chunk_size': request.form['chunk_size'],
            'current_frame': request.form['frame_start'],
            'filepath': request.form['filepath'],
            'render_settings': request.form['render_settings'],
            'status': 'running',
            'priority': 10,
            'owner': 'fsiddi'
        }

        http_request(BRENDER_SERVER, '/shots/add', shot_values)

        #  flashing does not work because we use redirect_url
        #  flash('New shot added!')

        return redirect(url_for('shots_index'))
    else:
        render_settings = json.loads(http_request(BRENDER_SERVER, '/render-settings/'))
        shows = json.loads(http_request(BRENDER_SERVER, '/shows/'))
        settings = json.loads(http_request(BRENDER_SERVER, '/settings/'))
        return render_template('add_shot_modal.html',
                            render_settings=render_settings,
                            settings=settings,
                            shows=shows)


@app.route('/jobs/')
def jobs_index():
    jobs = http_request(BRENDER_SERVER, '/jobs')
    #print(shots)
    jobs = json.loads(jobs)
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


def check_connection(host_address):
    try:
        http_request(host_address, '/')
        return "online"
    except:
        return "offline"


@app.route('/settings/', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        params = request.form
        http_request(BRENDER_SERVER, '/settings/update', params)

    shows = json.loads(http_request(BRENDER_SERVER, '/shows/'))
    settings = json.loads(http_request(BRENDER_SERVER, '/settings/'))
    return render_template('settings.html',
                           title='settings',
                           settings=settings,
                           shows=shows)


@app.route('/render-settings/', methods=['GET'])
def render_settings():
    render_settings = json.loads(http_request(BRENDER_SERVER, '/render-settings/'))
    return render_template('render_settings.html',
                           title='render settings',
                           render_settings=render_settings)


@app.route('/status/', methods=['GET'])
def status():
    try:
        server_status = check_connection(BRENDER_SERVER)
        server_stats = json.loads(http_request(BRENDER_SERVER, '/stats'))
    except :
        server_status = 'offline'
        server_stats = ''
    return render_template('status.html',
                           title='server status',
                           server_stats=server_stats,
                           server_status=server_status)


@app.route('/log/', methods=['GET', 'POST'])
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


@app.route('/sandbox/')
def sandbox():
    return render_template('sandbox.html', title='sandbox')


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404_error.html'), 404

app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'

if __name__ == "__main__":
    app.run()
