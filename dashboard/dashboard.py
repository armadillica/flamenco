import glob
import json
import os
import time
import urllib

from flask import (flash,
                   Flask,
                   jsonify,
                   redirect,
                   render_template,
                   request,
                   url_for)

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


@app.route('/workers/render_chunk', methods=['POST'])
def workers_render_chunk():
    #arguments = '-al'
    #command = 'ls'
    ##params = urllib.urlencode({'command': 'command',
    #                            'arguments': 'arguments'})
    f = urllib.urlopen("http://" + BRENDER_SERVER + "/workers/render_chunk")

    return jsonify(status='ok')


@app.route('/worker/<worker_id>')
def worker(worker_id):
    data = []
    #print(workers)
    workers = http_request(BRENDER_SERVER, '/workers')
    workers = json.loads(workers)
    if worker_id in workers:
        for key, val in workers.iteritems():
            if worker_id in key:
                print val['ip_address']
                try:
                    worker = http_request(val['ip_address'], '/run_info')
                    worker = json.loads(worker)
                    entry = ({"ip_address": val['ip_address']})
                    worker.update(entry)
                    print worker
                except IOError:
                   worker = {
                   u'status': u'N/A',
                   u'update_frequent': {
                        u'load_average': {
                            u'5min': 'N/A',
                            u'1min': 'N/A',
                            u'15min': 'N/A'
                        },
                        u'worker_num_cpus': 'N/A',
                        u'worker_cpu_percent': 'N/A',
                        u'worker_architecture': u'N/A',
                        u'worker_mem_percent': 'N/A',
                        u'worker_disk_percent': 'N/A'},
                        u'hostname': u'N/A',
                        u'system': u'N/A',
                        u'mac_address': 'N/A'
                    }

    #             work.append({
    #                 "worker_hostname": val['hostname'],
    #                 "worker_ip": val['ip_address'],
    #                 "worker_status": val['status']
    #                 })

    data.append({"worker_id": worker_id})
    data.append({"blabla": 'another blabla'})
    print data
    return render_template('worker.html', data=data, worker=worker, title='worker')


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


@app.route('/shots/delete', methods=['POST'])
def shots_delete():
    shot_ids = request.form['id']
    print(shot_ids)
    params = {'id': shot_ids}
    shots = http_request(BRENDER_SERVER, '/shots/delete', params)
    return 'done'


@app.route('/shots/update', methods=['POST'])
def shots_start():
    status = request.form['status'].lower()
    shot_ids = int(request.form['id'])
    if status in ['start', 'stop']:
        shots = http_request(BRENDER_SERVER,
                             '/shots/%s/%d' % (status, shot_ids))
        return 'done'
    else:
        return 'error'


@app.route('/shots/add', methods=['GET', 'POST'])
def shots_add():
    if request.method == 'POST':
        shot_values = {
            'production_shot_id': 1,
            'shot_name': request.form['shot_name'],
            'frame_start': request.form['frame_start'],
            'frame_end': request.form['frame_end'],
            'chunk_size': request.form['chunk_size'],
            'current_frame': request.form['frame_start'],
            'filepath': request.form['filepath'],
            'render_settings': 'will refer to settings table',
            'status': 'running',
            'priority': 10,
            'owner': 'fsiddi'
        }

        http_request(BRENDER_SERVER, '/shots/add', shot_values)

        #  flashing does not work because we use redirect_url
        #  flash('New shot added!')

        return redirect(url_for('shots_index'))
    else:
        return render_template('add_shot.html', title='add_shot')


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

        settings = json.loads(http_request(BRENDER_SERVER, '/settings/'))
        return render_template('settings.html',
                               title='settings',
                               settings=settings)

    else:
        settings = json.loads(http_request(BRENDER_SERVER, '/settings/'))
        return render_template('settings.html',
                               title='settings',
                               settings=settings)


@app.route('/status/', methods=['GET'])
def status():
    server_status = check_connection(BRENDER_SERVER)
    return render_template('status.html',
                           title='status',
                           server_status=server_status)


@app.route('/log/', methods=['GET', 'POST'])
def log():

    if request.method == 'POST':
        result = request.form['result']
        if result:
            try:
                file = open(result)
                lines = file.readlines()
                return render_template('log.html',
                                       title='status',
                                       lines=lines,
                                       result=result)
            except IOError:
                flash('Couldn\'t open file. ' +
                      'Please make sure the log file exists at ' + result)
        else:
            flash('No log to read Please input a filepath ex: ' +
                  '/User/koder/log.log')
    return render_template('log.html', title='status')


@app.route('/sandbox/')
def sandbox():
    return render_template('sandbox.html', title='sandbox')


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404_error.html'), 404

app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'

if __name__ == "__main__":
    app.run()
