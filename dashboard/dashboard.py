import urllib
import time
import json
import os 
import glob

from flask import Flask, render_template, jsonify, redirect, url_for, request, flash

BRENDER_SERVER = 'brender-server:9999'

def http_request(ip_address, method, post_params = False):
    # post_params must be a dictionnary
    if post_params:
        params = urllib.urlencode(post_params)
        f = urllib.urlopen('http://' + ip_address + method, params)
    else:
        f = urllib.urlopen('http://' + ip_address + method)
    
    print 'message sent, reply follows:'
    return f.read()

app = Flask(__name__)
app.config.update(
	DEBUG=True,
	SERVER_NAME='brender-flask:8888'
)


@app.route('/')
def index():
    return redirect(url_for('workers'))

@app.route('/workers/')
def workers():
    workers = http_request(BRENDER_SERVER, '/workers')
    #print workers
    workers = json.loads(workers)
    workers_list = []

    for key, val in workers.iteritems():
        val['checkbox'] = '<input type="checkbox" />'
        workers_list.append({
            "DT_RowId" : "worker_" + str(val['id']),
            "0" : val['checkbox'], 
            "1" : key, 
            "2" : val['system'],
            "3" : val['ip_address'], 
            "4" : val['connection'],
            "5" : val['status']
        })
        #print v

    entries = json.dumps(workers_list)

    return render_template('workers.html', entries=entries, title='workers')

@app.route('/workers/edit', methods=['POST'])
def workers_edit():
    worker_ids = request.form['id']
    worker_status = request.form['status']

    worker_config = {'system' : 'linux', 'blender': 'local'}
    params = urllib.urlencode({'id': worker_ids, 'status': worker_status, 'config' : worker_config})
    f = urllib.urlopen("http://brender-server:9999/workers/edit", params)

    return jsonify (status = 'ok')

@app.route('/workers/run_command', methods=['POST'])
def workers_run_command():
    arguments = '-al'
    command = 'ls'
    #params = urllib.urlencode({'command': 'command', 'arguments': 'arguments'})
    f = urllib.urlopen("http://brender-server:9999/workers/run_command")

    return jsonify (status = 'ok')



@app.route('/shots/')
def shots_index():
    shots = http_request(BRENDER_SERVER, '/shots')
    #print shots
    shots = json.loads(shots)
    shots_list = []

    for key, val in shots.iteritems():
        val['checkbox'] = '<input type="checkbox" value="' +  key + '" />'
        shots_list.append({
            "DT_RowId" : "shot_" + str(key),
            "0" : val['checkbox'], 
            "1" : key, 
            "2" : val['shot_name'], 
            "3" : val['percentage_done'], 
            "4" : val['render_settings'],
            "5" : val['status']
            })
        #print v

    entries = json.dumps(shots_list)
    
    return render_template('shots.html', entries=entries, title='shots')

@app.route('/shots/delete' , methods=['POST'])
def shots_delete():
    shot_ids = request.form['id']
    print shot_ids
    params = {'id': shot_ids }
    shots = http_request(BRENDER_SERVER, '/shots/delete', params)
    return 'done'

@app.route('/shots/update' , methods=['POST'])
def shots_start():
    status = request.form['status']
    shot_ids = request.form['id']
    params = {'id': shot_ids, 'status' : status}
    shots = http_request(BRENDER_SERVER, '/shots/update', params)
    return 'done'
    
    
@app.route('/shots/add' , methods=['GET', 'POST'])
def shots_add():
    if request.method == 'POST':
        shot_values = {
            'production_shot_id' : 1,
            'shot_name' : request.form['shot_name'],
            'frame_start' : request.form['frame_start'],
            'frame_end' : request.form['frame_end'],
            'chunk_size' : request.form['chunk_size'],
            'current_frame' : request.form['frame_start'],
            'filepath' : request.form['filepath'],
            'render_settings' : 'will refer to settings table',
            'status' : 'running',
            'priority' : 10,
            'owner' : 'fsiddi'
        }


        return http_request(BRENDER_SERVER, '/shots/add', shot_values)
    else:
        return render_template('add_shot.html', title='add_shot')


@app.route('/jobs/')
def jobs_index():
    jobs = http_request(BRENDER_SERVER, '/jobs')
    #print shots
    jobs = json.loads(jobs)
    jobs_list = []

    for key, val in jobs.iteritems():
        val['checkbox'] = '<input type="checkbox" value="' +  key + '" />'
        jobs_list.append({
            "DT_RowId" : "worker_" + str(key),
            "0" : val['checkbox'],
            "1" : key, 
            "2" : val['percentage_done'], 
            "3" : val['priority'],
            "4" : val['status']
            })
        #print v

    entries = json.dumps(jobs_list)
    
    return render_template('jobs.html', entries=entries, title='jobs')

def check_connection(host_address):
	try:
		http_request(host_address, '/')
		return "online"
	except:
		return "offline"		

@app.route('/status/', methods=['GET'])
def status():
    server_status = check_connection(BRENDER_SERVER)
    return render_template('status.html', title='status', server_status=server_status)


@app.route('/log/', methods=['GET','POST'])
def log():

    if request.method == 'POST':
        result = request.form['result']
        if result:
            file = open(result)
            lines = file.readlines()
            return render_template('log.html', title='status', lines=lines, result=result)
        else:
            flash('No Log Path')
    return render_template('log.html', title='status')


@app.route('/sandbox/')
def sandbox():
    return render_template('sandbox.html', title='sandbox')

@app.errorhandler(404)
def page_not_found(error):
	return render_template('404_error.html'),404

app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'

if __name__ == "__main__":
    app.run()
