import socket
import urllib
import time
import sys

from multiprocessing import Process
from flask import Flask, render_template, jsonify, redirect, url_for, request
from uuid import getnode as get_mac_address

BRENDER_SERVER = 'http://brender-server:9999'
MAC_ADDRESS = get_mac_address()  # the MAC address of the worker
HOSTNAME = socket.gethostname()  # the hostname of the worker

if (len(sys.argv) > 1):
    PORT = sys.argv[1]
else:
    PORT = 5000

# we get the IP address and attach the port number to it
IP_ADDRESS = socket.gethostbyname(HOSTNAME) + ':' + str(PORT)

# we initialize the app
app = Flask(__name__)
app.config.update(
    DEBUG = True,
    #SERVER_NAME = 'brender-worker:' + str(PORT)
)


# this is going to be an HTTP request to the server with all the info
# for registering the render node
def register_worker():
    print 'We register the node in 1 second!'
    time.sleep(1) 

    values = {
        'mac_address': MAC_ADDRESS,
        'ip_address': IP_ADDRESS,
        'hostname': HOSTNAME
        }

    params = urllib.urlencode(values)
    f = urllib.urlopen(BRENDER_SERVER + '/connect', params)
    #print f.read()

# we use muliprocessing to register the client the worker to the server
# while the worker app starts up
def start_worker():
        registration_process = Process(target=register_worker)
        registration_process.start()
        app.run(host='0.0.0.0')
        registration_process.join()
        
        
@app.route('/')
def index():
    return redirect(url_for('info'))

@app.route('/info')
def info():
    return jsonify(status = 'running',
        ip_address = IP_ADDRESS,
        mac_address = MAC_ADDRESS,
        hostname = HOSTNAME)

@app.route('/run_job', methods=['POST'])
def run_job():
    print request.form['command']
    return jsonify(status = 'ok')

@app.route('/update', methods=['POST'])
def update():
    print 'updating'
    return 'done'

if __name__ == "__main__":
    start_worker()
