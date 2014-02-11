import socket
import urllib
import time
import sys
import subprocess
import platform
import flask
import os
import select
from threading import Thread
from flask import Flask, redirect, url_for, request, jsonify
from uuid import getnode as get_mac_address

BRENDER_SERVER = 'http://brender-server:9999'
MAC_ADDRESS = get_mac_address()  # the MAC address of the worker
HOSTNAME = socket.gethostname()  # the hostname of the worker
SYSTEM = platform.system() + ' ' + platform.release()
PORT = 5000

app = Flask(__name__)
app.config.update(
    DEBUG=True,
)

def http_request(command, values):
    params = urllib.urlencode(values)
    try:
        urllib.urlopen(BRENDER_SERVER + '/' + command, params)
        #print(f.read())
    except IOError:
        print("[Warning] Could not connect to server to register")


# this is going to be an HTTP request to the server with all the info
# for registering the render node
def register_worker():
    import httplib
    while True:
        try:
            connection = httplib.HTTPConnection('127.0.0.1', PORT)
            connection.request("GET", "/info")
            break
        except socket.error:
            pass
        time.sleep(0.1)

    http_request('connect', {'mac_address': MAC_ADDRESS,
                                       'port': PORT,
                                       'hostname': HOSTNAME,
                                       'system': SYSTEM})


# we use muliprocessing to register the client the worker to the server
# while the worker app starts up
def start_worker():
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        register_thread = Thread(target=register_worker)
        register_thread.setDaemon(False)
        register_thread.start()

    from worker import controllers
    
    app.run(host='0.0.0.0')
