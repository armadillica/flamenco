import urllib
import time
import json

from flask import Flask, render_template, jsonify, redirect, url_for, request

BRENDER_SERVER = 'brender-server:9999'

def http_request(ip_address, method, post_params = False):
    # post_params must be a dictionay
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


@app.route("/")
def index():
    return redirect(url_for('workers'))

@app.route("/workers/")
def workers():
    workers = http_request(BRENDER_SERVER, '/workers')
    #print shots
    workers = json.loads(workers)
    workers_list = []

    for key, val in workers.iteritems():
        val['checkbox'] = '<input type="checkbox" />'
        workers_list.append({
            "DT_RowId" : "worker_" + str(val['id']),
            "0" : val['checkbox'], 
            "1" : key, 
            "2" : val['ip_address'], 
            "3" : val['connection'],
            "4" :val['status']
        })
        #print v

    entries = json.dumps(workers_list)

    return render_template('workers.html', entries=entries, title='workers')

@app.route("/workers/edit", methods=['POST'])
def workers_edit():
    worker_ids = request.form['id']
    worker_status = request.form['status']

    worker_config = {'system' : 'linux', 'blender': 'local'}
    params = urllib.urlencode({'id': worker_ids, 'status': worker_status, 'config' : worker_config})
    f = urllib.urlopen("http://brender-server:9999/workers/edit", params)

    return jsonify (status = 'ok')


@app.route("/shots/")
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
            "2" : val['percentage_done'], 
            "3" : val['render_settings'],
            "4" : val['status']
            })
        #print v

    entries = json.dumps(shots_list)
    
    return render_template('shots.html', entries=entries, title='shots')

@app.route("/shots/delete" , methods=['POST'])
def shots_delete():
    shot_ids = request.form['id']
    print shot_ids
    params = {'id': shot_ids }
    shots = http_request(BRENDER_SERVER, '/shots/delete', params)
    return 'done'

@app.route("/jobs/")
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

if __name__ == "__main__":
    app.run()
