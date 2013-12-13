import socket
import urllib
import time
import sys
import subprocess
import platform
import psutil
import flask
import os
import select
import gocept.cache.method
from threading import Thread
from flask import Flask, redirect, url_for, request, jsonify
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
    DEBUG=True
    #SERVER_NAME = 'brender-worker:' + str(PORT)
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


def _interactiveReadProcess(process, job_id):
    full_buffer = ''
    tmp_buffer = ''
    while True:
        tmp_buffer += _checkProcessOutput(process)
        if tmp_buffer:
            # http_request("update_blender_output_from_i_dont_know", tmp_buffer)
            pass
        full_buffer += tmp_buffer
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
    return jsonify(mac_address=MAC_ADDRESS,
                   hostname=HOSTNAME,
                   system=SYSTEM)


def run_blender_in_thread(options):
    """We build the command to run blender in a thread
    """
    render_command = [
        options['blender_path'],
        '--background',
        options['file_path'],
        '--python',
        options['render_settings'],
        '--frame-start' ,
        options['start_frame'],
        '--frame-end',
        options['end_frame'],
        '--render-anim',
        '--enable-autoexec'
        ]

    print("[Info] Running %s" % render_command)

    process = subprocess.Popen(render_command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    #flask.g.blender_process = process
    (retcode, full_output) = _interactiveReadProcess(process, options["job_id"])
    #flask.g.blender_process = None
    print(full_output)
    with open('log.log', 'w') as f:
        f.write(full_output)

    http_request('jobs/update', {'id': options['job_id'],
                                           'status': 'finished'})


@app.route('/execute_job', methods=['POST'])
def execute_job():
    options = {
        'job_id': request.form['job_id'],
        'file_path': request.form['file_path'],
        'blender_path': request.form['blender_path'],
        'start_frame': request.form['start'],
        'end_frame': request.form['end'],
        'render_settings': request.form['render_settings']
    }

    render_thread = Thread(target=run_blender_in_thread, args=(options,))
    render_thread.start()

    return jsonify(status='worker is running the command')


@app.route('/update', methods=['POST'])
def update():
    print('updating')
    blender_process = flask.g.get("blender_process")
    if blender_process:
        blender_process.kill()
    return('done')


def online_stats(system_stat):
    if 'blender_cpu' in [system_stat]:
        try:
            find_blender_process = [x for x in psutil.process_iter() if x.name == 'blender']
            cpu = []
            if find_blender_process:
                for process in find_blender_process:
                    cpu.append(process.get_cpu_percent())
                    print sum(cpu)
                    return round(sum(cpu), 2)
            else:
                return int(0)
        except psutil._error.NoSuchProcess:
            return int(0)
    if 'blender_mem' in [system_stat]:
        try:
            find_blender_process = [x for x in psutil.get_process_list() if x.name == 'blender']
            mem = []
            if find_blender_process:
                for process in find_blender_process:
                    mem.append(process.get_memory_percent())
                    return round(sum(mem), 2)
            else:
                return int(0)
        except psutil._error.NoSuchProcess:
            return int(0)
    if 'system_cpu' in [system_stat]:
        cputimes_idle = psutil.cpu_times_percent(interval=0.5).idle
        cputimes = round(100 - cputimes_idle, 2)
        return cputimes
    if 'system_mem' in [system_stat]:
        mem_percent = psutil.phymem_usage().percent
        return mem_percent
    if 'system_disk' in [system_stat]:
        disk_percent = psutil.disk_usage('/').percent
        return disk_percent


def offline_stats(offline_stat):
    if 'number_cpu' in [offline_stat]:
        return psutil.NUM_CPUS

    if 'arch' in [offline_stat]:
        return platform.machine()

    '''
        TODO
        1. [Coming Soon] Add save to database for offline stats
        2. [Fixed] find more cpu savy way with or without psutil
        3. [Fixed] seems like psutil uses a little cpu when its checks cpu_percent
        it goes to 50+ percent even though the system shows 5 percent
    '''


def get_system_load_frequent():
    load = os.getloadavg()
    time.sleep(0.5)
    return ({
        "load_average": ({
            "1min": round(load[0], 2),
            "5min": round(load[1], 2),
            "15min": round(load[2], 2)
            }),
        "worker_cpu_percent": online_stats('system_cpu'),
        'worker_blender_cpu_usage': online_stats('blender_cpu')
        })


@gocept.cache.method.Memoize(120)
def get_system_load_less_frequent():
    time.sleep(0.5)
    return ({
        "worker_num_cpus": offline_stats('number_cpu'),
        "worker_architecture": offline_stats('arch'),
        "worker_mem_percent": online_stats('system_mem'),
        "worker_disk_percent": online_stats('system_disk'),
        "worker_blender_mem_usage": online_stats('blender_mem')
        })


@app.route('/run_info')
def run_info():
    print('[Debug] get_system_load for %s') % HOSTNAME

    return jsonify(mac_address=MAC_ADDRESS,
                   hostname=HOSTNAME,
                   system=SYSTEM,
                   update_frequent=get_system_load_frequent(),
                   update_less_frequent=get_system_load_less_frequent()
                   )

if __name__ == "__main__":
    start_worker()
