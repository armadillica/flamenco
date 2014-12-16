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
import Queue # for windows
from flask import Flask
from flask import redirect
from flask import url_for
from flask import request
from flask import jsonify
from uuid import getnode as get_mac_address

MAC_ADDRESS = get_mac_address()  # the MAC address of the worker
HOSTNAME = socket.gethostname()  # the hostname of the worker
SYSTEM = platform.system() + ' ' + platform.release()
PROCESS = None

if platform.system() is not 'Windows':
    from fcntl import fcntl, F_GETFL, F_SETFL

app = Flask(__name__)

BRENDER_SERVER = ''

def http_request(command, values):
    params = urllib.urlencode(values)
    try:
        urllib.urlopen('http://' + BRENDER_SERVER + '/' + command, params)
        #print(f.read())
    except IOError:
        print("[Warning] Could not connect to server to register")

# this is going to be an HTTP request to the server with all the info
# for registering the render node
def register_worker():
    import httplib
    while True:
        try:
            connection = httplib.HTTPConnection('127.0.0.1', app.config['PORT'])
            connection.request("GET", "/info")
            break
        except socket.error:
            pass
        time.sleep(0.1)

    http_request('connect', {'mac_address': MAC_ADDRESS,
                                       'port': app.config['PORT'],
                                       'hostname': HOSTNAME,
                                       'system': SYSTEM})

def _checkProcessOutput(process):
    ready = select.select([process.stdout.fileno(),
                           process.stderr.fileno()],
                          [], [])
    full_buffer = ''
    for fd in ready[0]:
        while True:
            try:
                buffer = os.read(fd, 1024)
                if not buffer:
                    break
                print buffer
            except OSError:
                break
            full_buffer += buffer
    return full_buffer

def _checkOutputThreadWin(fd, q):
    while True:
        buffer = os.read(fd, 1024)
        if not buffer:
            break
        else:
            print buffer
            q.put(buffer)


def _checkProcessOutputWin(process, q):
    full_buffer = ''
    while True:
        try:
            buffer = q.get_nowait()
            if not buffer:
                break
        except:
            break
        full_buffer += buffer
    return full_buffer

def _interactiveReadProcessWin(process, task_id):
    full_buffer = ''
    tmp_buffer = ''
    q = Queue.Queue()
    t_out = Thread(target=_checkOutputThreadWin, args=(process.stdout.fileno(), q,))
    t_err = Thread(target=_checkOutputThreadWin, args=(process.stderr.fileno(), q,))

    t_out.start()
    t_err.start()

    while True:
        tmp_buffer += _checkProcessOutputWin(process, q)
        if tmp_buffer:
            pass
        full_buffer += tmp_buffer
        if process.poll() is not None:
            break

    t_out.join()
    t_err.join()
    full_buffer += _checkProcessOutputWin(process, q)
    return (process.returncode, full_buffer)

def _interactiveReadProcess(process, task_id):
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
        '--render-output',
        options['output'],
        '--python',
        options['render_settings'],
        '--frame-start' ,
        options['start_frame'],
        '--frame-end',
        options['end_frame'],
        '--render-format',
        options['format'],
        '--render-anim',
        '--enable-autoexec'
        ]

    print("[Info] Running %s" % render_command)

    PROCESS = subprocess.Popen(render_command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

    # Make I/O non blocking for unix
    if platform.system() is not 'Windows':
        flags = fcntl(PROCESS.stdout, F_GETFL)
        fcntl(PROCESS.stdout, F_SETFL, flags | os.O_NONBLOCK)
        flags = fcntl(process.stderr, F_GETFL)
        fcntl(PROCESS.stderr, F_SETFL, flags | os.O_NONBLOCK)

    #flask.g.blender_process = process
    (retcode, full_output) =  _interactiveReadProcess(PROCESS, options["task_id"]) \
        if (platform.system() is not "Windows") \
        else _interactiveReadProcessWin(PROCESS, options["task_id"])

    print ('[DEBUG] return code: %d') % retcode

    #flask.g.blender_process = None
    #print(full_output)
    script_dir = os.path.dirname(__file__)
    rel_path = 'render_log_' + HOSTNAME + '.log'
    abs_file_path = os.path.join(script_dir, rel_path)
    with open(abs_file_path, 'w') as f:
        f.write(full_output)

    if retcode == 137:
        http_request('tasks', {'id': options['task_id'],
                                            'status': 'aborted'})
    elif retcode != 0:
        http_request('tasks', {'id': options['task_id'],
                                            'status': 'failed'})
    else:
        http_request('tasks', {'id': options['task_id'],
                                           'status': 'finished'})


@app.route('/execute_task', methods=['POST'])
def execute_task():
    options = {
        'task_id': request.form['task_id'],
        'file_path': request.form['file_path'],
        'blender_path': request.form['blender_path'],
        'start_frame': request.form['start'],
        'end_frame': request.form['end'],
        'render_settings': request.form['render_settings'],
        'output': request.form['output'],
        'format': request.form['format']
    }

    render_thread = Thread(target=run_blender_in_thread, args=(options,))
    render_thread.start()

    while PROCESS is None:
        time.sleep(1)

    return jsonify(pid=PROCESS.pid)

@app.route('/pid')
def get_pid():
    response = dict(pid=PROCESS.pid)
    return jsonify(response)

@app.route('/command', methods=['HEAD']):
def get_command():
    return '', 503



@app.route('/kill/<int:pid>', methods=['DELETE'])
def update():
    print('killing')
    if platform.system() is 'Windows':
        kill(pid, CTRL_C_EVENT)
    else:
        kill(pid, SIGKILL)

    return '', 204


def online_stats(system_stat):
    '''
    if 'blender_cpu' in [system_stat]:
        try:
            find_blender_process = [x for x in psutil.process_iter() if x.name == 'blender']
            cpu = []
            if find_blender_process:
                for process in find_blender_process:
                    cpu.append(process.get_cpu_percent())
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
    '''

    if 'system_cpu' in [system_stat]:
        try:
            cputimes = psutil.cpu_percent(interval=1)
            return cputimes
        except:
            return int(0)
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


@gocept.cache.method.Memoize(5)
def get_system_load_frequent():
    if platform.system() is not "Windows":
        load = os.getloadavg()
        return ({
            "load_average": ({
                "1min": round(load[0], 2),
                "5min": round(load[1], 2),
                "15min": round(load[2], 2)
                }),
            "worker_cpu_percent": online_stats('system_cpu'),
            #'worker_blender_cpu_usage': online_stats('blender_cpu')
            })
    else:
        # os.getloadavg does not exists on Windows
        return ({
            "load_average":({
                "1min": '?',
                "5min": '?',
                "15min": '?'
            }),
           "worker_cpu_percent": online_stats('system_cpu')
        })

@gocept.cache.method.Memoize(120)
def get_system_load_less_frequent():
    return ({
        "worker_num_cpus": offline_stats('number_cpu'),
        "worker_architecture": offline_stats('arch'),
        "worker_mem_percent": online_stats('system_mem'),
        "worker_disk_percent": online_stats('system_disk'),
        # "worker_blender_mem_usage": online_stats('blender_mem')
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
