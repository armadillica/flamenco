import socket
import urllib
import time

from multiprocessing import Process
from flask import Flask, render_template, jsonify, redirect, url_for
from uuid import getnode as get_mac_address

MAC_ADDRESS = get_mac_address()  # the MAC address of the worker
HOSTNAME = socket.gethostname()  # the hostname of the worker
IP_ADDRESS = socket.gethostbyname(HOSTNAME + '.local')

# we initialize the app
app = Flask(__name__)
app.debug = True


# this is going to be an HTTP request to the server with all the info
# for registering the render node
def register_worker():
    print 'We register the node in 1 second!'
    time.sleep(1) 

    values = {
        'mac_address': MAC_ADDRESS,
        'ip_address': IP_ADDRESS
        }

    params = urllib.urlencode(values)
    f = urllib.urlopen("http://brender-server:9999/connect", params)
    print f.read()

# we use muliprocessing to register the client the worker to the server
# while the worker app starts up
def start_worker():
        registration_process = Process(target=register_worker)
        registration_process.start()
        app.run()
        registration_process.join()
        
        
@app.route("/")
def index():
    return redirect(url_for('info'))

@app.route("/info")
def info():
    return jsonify(status = 'running',
        ip_address = IP_ADDRESS,
        mac_address = MAC_ADDRESS,
        hostname = HOSTNAME)


if __name__ == "__main__":
    start_worker()
