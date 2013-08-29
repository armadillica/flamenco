import socket
import urllib
import time

from flask import Flask, render_template, jsonify, redirect, url_for, request
from model import *
from jobs import *
from uuid import getnode as get_mac

MAC_ADDR = get_mac()  # the MAC address of the client
HOSTNAME = socket.gethostname()


app = Flask(__name__)
app.config.update(
	DEBUG=True,
	SERVER_NAME='brender-server:9999'
)


@app.route("/")
def index():
	return redirect(url_for('info'))

@app.route("/info")
def info():
    return jsonify(status = 'running',
    	mac_addr = MAC_ADDR,
    	hostname = HOSTNAME)

@app.route('/workers/')
def workers():
    workers = {}
    for worker in Workers.select():
        try:
            f = urllib.urlopen('http://' + worker.ip_address)
            print f.read()
        except Exception, e:
            print e , '--> Worker', worker.hostname, 'not online'
            worker.status = 'offline'
            worker.save()
        
        workers[worker.hostname] = {
            "id": worker.id,
            "hostname" : worker.hostname,
            "status" : worker.status,
            "ip_address" : worker.ip_address}
    return jsonify(workers)

@app.route('/shots/')
def shots():
    shots = {}
    for shot in Shots.select():
        shots[shot.id] = {
            "frame_start" : shot.frame_start,
            "frame_end" : shot.frame_end,
            "current_frame" : shot.current_frame,
            "status" : shot.status}
    return jsonify(shots)

@app.route('/shots/start/<int:shot_id>')
def shot_start(shot_id):
    try:
        shot = Shots.get(Shots.id == shot_id)
    except Exception, e:
        print e , '--> Shot not found'
        return 'Shot not found'

    if shot.status == 'started':
        return 'Shot already started'
    else:
        shot.status = 'started'
        shot.save()
        http_request()
        return 'Shot started'

@app.route('/shots/add')
def shot_add():
    print 'adding shot'

    shot = Shots.create(
        production_shot_id = 1,
        frame_start = 2,
        frame_end = 50,
        chunk_size = 5,
        current_frame = 2,
        filepath = '/path',
        render_settings = 'will refer to settings table',
        status = 'running',
        priority = 10,
        owner = 'fsiddi')

    print 'parsing shot'

    create_jobs(shot)

    print 'refresh list of available workers'

    dispatch_jobs()

    return 'done'

@app.route('/jobs/')
def jobs():
    jobs = {}
    for job in Jobs.select():
        jobs[job.id] = {
            "chunk_start" : job.chunk_start,
            "chunk_end" : job.chunk_end,
            "current_frame" : job.current_frame,
            "status" : job.status}
    return jsonify(jobs)

@app.route('/connect', methods=['POST', 'GET'])
def connect():
    error = None
    if request.method == 'POST':
        #return str(request.json['foo'])
        
        #ip_address = request.form['ip_address']
        ip_address = '127.0.0.1:5000'
        mac_address = request.form['mac_address']
        hostname = request.form['hostname']

        worker = Workers.get(Workers.mac_address == mac_address)

        if worker:
            print('This worker connected before, updating IP address')
            worker.ip_address = ip_address
            worker.save()

        else:
            print('This worker never connected before')
            # create new worker object with some defaults. Later on most of these
            # values will be passed as JSON object during the first connection
            
            worker = Workers.create(
                hostname = hostname, 
                mac_address = mac_address, 
                status = 'enabled', 
                warning = False, 
                config = 'bla',
                ip_address = ip_address)
            
            print('Worker has been added')

        #params = urllib.urlencode({'worker': 1, 'eggs': 2})
        
        # we verify the identity of the worker (will check on database)
        f = urllib.urlopen('http://' + ip_address)
        print 'The following worker just connected:'
        print f.read()
        
        return ip_address
    # the code below is executed if the request method
    # was GET or the credentials were invalid
    return jsonify(error = error)

@app.route('/order', methods=['POST'])
def order():
    return 'aa'

if __name__ == "__main__":
    app.run()
