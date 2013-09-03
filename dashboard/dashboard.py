import urllib
import time
import json

from flask import Flask, render_template, jsonify, redirect, url_for, request

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
    workers = http_request('brender-server:9999', '/workers')
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


    return render_template('workers.html', entries=entries)

if __name__ == "__main__":
    app.run()
