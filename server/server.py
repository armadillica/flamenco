import socket
import urllib
import time

from flask import Flask, render_template, jsonify, redirect, url_for, request
from model import *
from uuid import getnode as get_mac

MAC_ADDR = get_mac()  # the MAC address of the client
HOSTNAME = socket.gethostname()


app = Flask(__name__)
app.config.update(
	DEBUG=True,
	SERVER_NAME='brender-server:9999'
)

def send_orders():
    for worker in Workers.select().where(Workers.status == 'available'):
        print worker.hostname

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
            f = urllib.urlopen('http://' + worker.ip_address + ':' + str(worker.port))
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
        send_orders()
        return 'Shot started'
    

@app.route('/connect', methods=['POST', 'GET'])
def login():
    error = None
    if request.method == 'POST':
        #return str(request.json['foo'])
        
        #ip_address = request.form['ip_address']
        ip_address = '127.0.0.1'
        port = request.form['port']
        mac_address = request.form['mac_address']
        hostname = request.form['hostname']

        worker = Workers.get(Workers.mac_address == mac_address)

        if worker:
            print('This worker connected before, updating IP address')
            worker.ip_address = ip_address
            worker.port = port
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
                ip_address = ip_address,
                port = port)
            
            print('Worker has been added')

        #params = urllib.urlencode({'worker': 1, 'eggs': 2})
        
        # we verify the identity of the worker (will check on database)
        f = urllib.urlopen('http://' + ip_address + ':' + port)
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
