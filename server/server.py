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
        
        #ip_address = request.form['ip_address']
        ip_address = '127.0.0.1'
        port = request.form['port']
        mac_address = request.form['mac_address']

        try:
            worker = Clients.get(Clients.mac_address == mac_address)
            print('This worker connected before')

        except:
            print('This worker never connected before')
            # create new worker object with some defaults. Later on most of these
            # values will be passed as JSON object during the first connection
            
            worker = Clients.create(
                hostname = line[1], 
                mac_address = line[0], 
                status = 'enabled', 
                warning = False, 
                config = 'bla')
            
            clients_dict[line[0]] = socket;

        #params = urllib.urlencode({'worker': 1, 'eggs': 2})
        
        # we verify the identity of the worker (will check on database)
        f = urllib.urlopen('http://' + ip_address + ':' + port)
        print 'The following worker just connected:'
        print f.read()
        
        return ip_address
    # the code below is executed if the request method
    # was GET or the credentials were invalid
    return jsonify(error = error)

if __name__ == "__main__":
    start_worker()
