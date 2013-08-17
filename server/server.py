import socket
import urllib
import time

from flask import Flask, render_template, jsonify, redirect, url_for, request
from uuid import getnode as get_mac

MAC_ADDR = get_mac()  # the MAC address of the client
HOSTNAME = socket.gethostname()

app = Flask(__name__)
app.config.update(
	DEBUG=True,
	SERVER_NAME='brender-server:9999'
)

def ping_server():
	print 'We are starting!'

def start_worker():
        ping_server()
        app.run()

@app.route("/")
def index():
	return redirect(url_for('info'))

@app.route("/info")
def info():
    return jsonify(status = 'running',
    	mac_addr = MAC_ADDR,
    	hostname = HOSTNAME)

@app.route('/hellos/')
def clients():
    return 'hellos!'


@app.route('/hellos/<int:client_id>')
def hello(client_id):
    return 'client %d' % client_id

@app.route('/connect', methods=['POST', 'GET'])
def login():
    error = None
    if request.method == 'POST':
        #return str(request.json['foo'])
        #params = urllib.urlencode({'client': 1, 'eggs': 2})
        
        # we verify the identity of the worker (will check on database)
        f = urllib.urlopen("http://127.0.0.1:5000/")
        print 'The following worker just connected:'
        print f.read()
        ip_address = request.form['ip_address']
        mac_address = request.form['mac_address']
        return ip_address
    # the code below is executed if the request method
    # was GET or the credentials were invalid
    return jsonify(error = error)

if __name__ == "__main__":
    start_worker()
