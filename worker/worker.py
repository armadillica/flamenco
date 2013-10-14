import socket
import urllib
import time
import sys
import subprocess
import platform

from multiprocessing import Process
from threading import Thread
from flask import Flask, render_template, jsonify, redirect, url_for, request
from uuid import getnode as get_mac_address

BRENDER_SERVER = 'http://brender-server:9999'
MAC_ADDRESS = get_mac_address()  # the MAC address of the worker
HOSTNAME = socket.gethostname()  # the hostname of the worker
SYSTEM = platform.system() + ' ' + platform.release()

if (len(sys.argv) > 1):
    PORT = sys.argv[1]
else:
    PORT = 5000

# we initialize the app
app = Flask(__name__)
app.config.update(
    DEBUG = True,
    #SERVER_NAME = 'brender-worker:' + str(PORT)
)


def send_command_to_server(command, values):
    params = urllib.urlencode(values)
    try:
        f = urllib.urlopen(BRENDER_SERVER + '/' + command, params)
        #print f.read()
        # TODO(fsiddi): Use proper exception filtering
    except:
        print "[Warning] Could not connect to server to register"


# this is going to be an HTTP request to the server with all the info
# for registering the render node
def register_worker():
    print 'We register the node in 1 second!'
    time.sleep(1)
    values = {
        'mac_address': MAC_ADDRESS,
        'port' : PORT,
        'hostname': HOSTNAME,
        'system' : SYSTEM,
        }
    send_command_to_server('connect', values)

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
        mac_address = MAC_ADDRESS,
        hostname = HOSTNAME,
        system = SYSTEM)

def run_blender_in_thread():
    """
    subp = subprocess.Popen(render_command, stdout=subprocess.PIPE, shell=True)
    (output, err) = subp.communicate()
    print output
    with open('log.log','w') as f:
        f.write(str(output))
    """
    send_command_to_server('update', {})

@app.route('/render_chunk', methods=['POST'])
def run_command():
    file_path = request.form['file_path']
    blender_path = request.form['blender_path']
    start = request.form['start']
    end = request.form['end']
    options = "-s %s -e %s -a" % (start, end)
    render_command = '%s -b %s %s' % (blender_path, file_path, options);
    print "I'm the worker and i run the following test command %s" % render_command

    render_thread = Thread(target=run_blender_in_thread)
    render_thread.start()

    return jsonify(status = 'ok command run')

@app.route('/run_job', methods=['POST'])
def run_job():
    print "we are running the job"
    # job is a stack of commands : pre-script, rendering, post-script
    return jsonify(status = 'ok')

@app.route('/update', methods=['POST'])
def update():
    print 'updating'
    return 'done'

if __name__ == "__main__":
    start_worker()
