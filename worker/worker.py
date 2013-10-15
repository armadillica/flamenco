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
    import httplib
    while True:
        try:
            connection = httplib.HTTPConnection('127.0.0.1', PORT)
            connection.request("GET", "/info")
            break
        except socket.error:
            pass
        time.sleep(0.1)

    send_command_to_server('connect', {
        'mac_address': MAC_ADDRESS,
        'port' : PORT,
        'hostname': HOSTNAME,
        'system' : SYSTEM,
        })

# we use muliprocessing to register the client the worker to the server
# while the worker app starts up
def start_worker():
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        register_thread = Thread(target=register_worker)
        register_thread.setDaemon(False)
        register_thread.start()

    app.run(host='0.0.0.0')

def _checkProcessOutput(process):
    ready = select.select([process.stdout.fileno(),
                           process.stderr.fileno()],
                          [], [])
    full_buffer = ''
    for fd in ready[0]:
        while True:
            buffer = os.read(fd, 1024)
            if not buffer:
                break
            full_buffer += buffer
    return full_buffer

def _interactiveReadProcess(process):
    full_buffer = ''
    while True:
        full_buffer += _checkProcessOutput(process)
        if process.poll() is not None:
            break
    # It might be some data hanging around in the buffers after
    # the process finished
    full_buffer += _checkProcessOutput(process)
    return (process.returncode, full_buffer)

@app.route('/')
def index():
    return redirect(url_for('info'))

@app.route('/info')
def info():
    return jsonify(status = 'running',
        mac_address = MAC_ADDRESS,
        hostname = HOSTNAME,
        system = SYSTEM)

def run_blender_in_thread(options):
    blender_options = "-s %s -e %s -a" % (options['start_frame'], options['end_frame'])
    render_command = '%s -b %s %s' % (options['blender_path'],
                                      options['file_path'],
                                      blender_options)
    print "I'm the worker and i run the following test command %s" % render_command

    process = subprocess.Popen(['blender', '-b', '-f', '1'],  # render_command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    #flask.g.blender_process = process
    (retcode, full_output) = _interactiveReadProcess(process)
    #flask.g.blender_process = None
    print(full_output)
    with open('log.log','w') as f:
        f.write(full_output)

    send_command_to_server('jobs/update', {'id': options['job_id'], 'status': 'finished'})

@app.route('/render_chunk', methods=['POST'])
def run_command():
    options = {
        'job_id': request.form['job_id'],
        'file_path': request.form['file_path'],
        'blender_path': request.form['blender_path'],
        'start_frame': request.form['start'],
        'end_frame': request.form['end']
    }

    render_thread = Thread(target=run_blender_in_thread, args=(options,))
    render_thread.start()

    return jsonify(status = 'ok command run')

@app.route('/update', methods=['POST'])
def update():
    print 'updating'
    blender_process = flask.g.get("blender_process")
    if blender_process:
        blender_process.kill()
    return 'done'

if __name__ == "__main__":
    start_worker()
