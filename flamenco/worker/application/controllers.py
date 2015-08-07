import socket
import urllib
import time
import subprocess
import platform
import os
import json
import shutil
import select
import requests
import logging
from zipfile import ZipFile
from zipfile import BadZipfile
from zipfile import zlib
from threading import Thread
from threading import Lock
from threading import Timer
import Queue # for windows

from flask import redirect
from flask import url_for
from flask import request
from flask import jsonify

from uuid import getnode as get_mac_address

from application import app
from application import clean_dir
from requests.exceptions import ConnectionError

MAC_ADDRESS = get_mac_address()  # the MAC address of the worker
HOSTNAME = socket.gethostname()  # the hostname of the worker
PLATFORM = platform.system()
SYSTEM = PLATFORM + ' ' + platform.release()
PROCESS = None
LOCK = Lock()
ACTIVITY = None
LOG = None
TIME_INIT = None
CONNECTIVITY = False
FLAMENCO_MANAGER = app.config['FLAMENCO_MANAGER']


if platform.system() is not 'Windows':
    from fcntl import fcntl, F_GETFL, F_SETFL
    from signal import SIGKILL
else:
    from signal import CTRL_C_EVENT


# def http_request(command, values):
#     global CONNECTIVITY
#     params = urllib.urlencode(values)
#     try:
#         urllib.urlopen('http://' + FLAMENCO_MANAGER + '/' + command, params)
#         #print(f.read())
#     except IOError:
#         CONNECTIVITY = False
#         logging.error("Could not connect to manager to register")

def http_request(ip_address, command, method, params=None, files=None):
    global CONNECTIVITY
    if method == 'delete':
        r = requests.delete('http://' + ip_address + command)
    elif method == 'post':
        r = requests.post('http://' + ip_address + command, data=params, files=files)
    elif method == 'get':
        r = requests.get('http://' + ip_address + command)
    elif method == 'put':
        r = requests.put('http://' + ip_address + command, data=params)
    elif method == 'patch':
        r = requests.patch('http://' + ip_address + command, data=params)

    if r.status_code == 404:
        return '', 404

    # Only for debug
    if r.status_code == 400:
        for chunk in r.iter_content(50):
            print chunk
        return '', 404

    if r.status_code == 204:
        return '', 204

    if r.status_code >= 500:
        logging.debug("STATUS CODE: %d" % r.status_code)
        return '', 500

    return r.json()

def register_worker():
    """This is going to be an HTTP request to the server with all the info
    for registering the render node.
    """
    global CONNECTIVITY

    while True:
        try:
            r = http_request(app.config['FLAMENCO_MANAGER'], '/', 'get')
            CONNECTIVITY = True
            break
        except ConnectionError:
            logging.error(
                "Could not connect to {0} to register".format(
                    app.config['FLAMENCO_MANAGER']))
            CONNECTIVITY = False
            pass
        time.sleep(1)

    http_request(app.config['FLAMENCO_MANAGER'], '/workers', 'post',
        params={
            'port': app.config['PORT'],
            'hostname': HOSTNAME,
            'system': SYSTEM})

def get_task():
    manager_url = "http://{0}/tasks".format(app.config['FLAMENCO_MANAGER'])
    return requests.get(manager_url)

def getZipFile(url, tmpfile, zippath, force=False):
    if not os.path.exists(tmpfile) or force:
        try:
            r = requests.get(url, stream=True)
        except KeyboardInterrupt:
            return

        with open(tmpfile, 'wb') as f:
            try:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        f.flush()
            except KeyboardInterrupt:
                return

    if not os.path.exists(zippath):
        os.mkdir(zippath)
    print ( "Extracting {0}".format(tmpfile))
    unzipok = True
    try:
        with ZipFile(tmpfile, 'r') as jobzip:
            try:
                jobzip.extractall(path=zippath)
            except KeyboardInterrupt:
                return
            except zlib.error:
                unzipok = False
    except BadZipfile, zlib.error:
        unzipok = False

    if not unzipok:
        print ("Removing bad zipfile {0}".format(tmpfile))
        os.remove(tmpfile)
        logging.error('Not a ZipFile')

    return unzipok

def update():
    global PROCESS
    global LOCK
    if not PROCESS:
        logging.info("No PROCESS")
        return '', 204

    logging.info("Killing {0}".format(PROCESS.pid))
    if platform.system() is 'Windows':
        os.kill(PROCESS.pid, CTRL_C_EVENT)
    else:
        os.kill(PROCESS.pid, SIGKILL)

    #LOCK.acquire()
    #PROCESS = None
    #LOCK.release()
    return '', 204

global LOOP_THREAD

def worker_loop():
    register_worker()
    print ("Quering for a new task")

    params = {'worker': HOSTNAME}
    manager_url = "http://{0}/tasks/compiled/0".format(
        app.config['FLAMENCO_MANAGER'])
    try:
        # Send a request to the manager, specifying our hostname
        rtask = requests.get(manager_url, params=params)
    except KeyboardInterrupt:
        return

    if rtask.status_code == 200:
        try:
            files = rtask.json()['files']
            task = rtask.json()['options']
        except:
            raise
            pass

        print ("New Task Found {0}, job {1}".format(task['task_id'], task['job_id']))
        params = {
            'status': 'active',
            'log': None,
            'activity': None,
            'time_cost': 0,
            'job_id': task['job_id'],
            }
        try:
            requests.patch(
                'http://' + app.config['FLAMENCO_MANAGER'] + '/tasks/' + str(task['task_id']),
            data = params
            )
            CONNECTIVITY = True
        except ConnectionError:
            logging.error(
                'Cant connect with the Manager {0}'.format(app.config['FLAMENCO_MANAGER']))
            CONNECTIVITY = False


        tmp_folder = os.path.join(app.config['TMP_FOLDER'], 'flamenco-worker')
        clean_dir(tmp_folder, task['job_id'])

        jobpath = os.path.join(app.config['TMP_FOLDER'],
                               'flamenco-worker',
                               str(task['job_id']))
        if not os.path.exists(jobpath):
            os.mkdir(jobpath)

        # Get job file
        print ("Fetching job file {0}".format(task['job_id']))
        zippath = os.path.join(jobpath, str(task['job_id']))
        tmpfile = os.path.join(
            jobpath, 'taskfile_{0}.zip'.format(task['job_id']))
        url = "http://{0}/tasks/zip/{1}".format(
                app.config['FLAMENCO_MANAGER'], task['job_id'])
        unzipok = getZipFile(url, tmpfile, zippath)

        # Get support file
        print ("Fetching support file {0}".format(task['job_id']))
        zippath = os.path.join(jobpath, str(task['job_id']))
        tmpfile = os.path.join(
            jobpath, 'tasksupportfile_{0}.zip'.format(task['job_id']))
        url = "http://{0}/tasks/zip/sup/{1}".format(
                app.config['FLAMENCO_MANAGER'], task['job_id'])
        unzipok = getZipFile(url, tmpfile, zippath, True)

        # Get dependency file
        zippath = os.path.join(jobpath, str(task['job_id']))
        tmpfile = os.path.join(
            jobpath, 'dependencies.zip'.format(task['job_id']))
        url = "http://{0}/tasks/zip/dep/{1}".format(
                app.config['FLAMENCO_MANAGER'], task['job_id'], task['task_id'])
        print ("Fetching dependency {0}".format(url))
        unzipdepok = getZipFile(url, tmpfile, zippath)

        # Get compiler settings
        r = None
        url = 'http://' + app.config['FLAMENCO_MANAGER'] + '/job-types/'
        try:
            r = requests.get(
                url + task['type'],
            )
        except ConnectionError:
            logging.error(
                'Can not connect with the Manager {0}'.format(FLAMENCO_MANAGER))

        task['compiler_settings'] = {}
        print (r.status_code)
        if r != None and r.status_code == 200:
            task['compiler_settings'] = r.json()

        if unzipok:
            execute_task(task, files)

    elif rtask.status_code == 403:
        print ("[{0}] Worker is disabled".format(HOSTNAME))
    elif rtask.status_code == 400:
        print ("[{0}] No task available".format(HOSTNAME))
    #LOOP_THREAD = Timer(5, worker_loop)
    #LOOP_THREAD.start()

def _checkProcessOutput(process):
    try:
        # If the PROCESS halts, will halt here
        ready = select.select([process.stdout.fileno(),
                            process.stderr.fileno()],
                            [], [])
    except KeyboardInterrupt:
        raise
        return
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

def send_thumbnail(manager_url, file_path, params):
    try:
        thumbnail_file = open(file_path, 'r')
    except IOError, e:
        logging.error('Cant open thumbnail: {0}'.format(e))
        return
    try:
        requests.post(manager_url, files={'file': thumbnail_file}, data=params)
    except ConnectionError:
        logging.error("Can't send Thumbnail to manager: {0}".format(manager_url))
    thumbnail_file.close()

def _parse_output(tmp_buffer, options):
    global ACTIVITY
    global LOG
    global TIME_INIT

    action = []

    task_id = options['task_id']
    module_name = 'application.task_parsers.{0}'.format(options['task_parser'])
    task_parser = None
    try:
        module_loader = __import__(module_name, globals(), locals(), ['task_parser'], 0)
        task_parser = module_loader.task_parser
    except ImportError, e:
        print('Cant find module {0}: {1}'.format(module_name, e))

    if not LOG:
        LOG = ""

    if task_parser:
        parser_output = task_parser.parse(tmp_buffer, options, ACTIVITY)
        if parser_output:
            ACTIVITY = parser_output
            activity = json.loads(parser_output)

        if activity.get('thumbnail'):
            params = dict(task_id=task_id)
            manager_url = "http://{0}/tasks/thumbnails".format(
                app.config['FLAMENCO_MANAGER'])
            request_thread = Thread(
                target=send_thumbnail,
                args=(manager_url, activity.get('thumbnail'), params))
            request_thread.start()

    time_init = TIME_INIT
    if time_init:
        time_cost=int(time.time())-time_init

    else:
        logging.error("time_init is None")
        time_cost = None

    params = {
        'status': 'active',
        'log': LOG[-256:],
        'activity': ACTIVITY,
        'time_cost': time_cost,
        'job_id': options['job_id'],
        'task_id': options['task_id'],
        }
    r = None
    try:
        r = requests.patch(
            'http://{0}/tasks/{1}'.format(
                app.config['FLAMENCO_MANAGER'], task_id),
            data=params,
        )
        CONNECTIVITY = True
    except ConnectionError:
        logging.error(
            'Cant connect with the Manager {0}'.format(FLAMENCO_MANAGER))
        CONNECTIVITY = False

    if r != None and r.status_code != 204:
        print ("Stopping Task: {0}".format(r.status_code))
        action.append('stop')

    #if activity.get('path_not_found'):
    #    print ("Path not Found")
    #    # action.append('stop')

    LOG = "{0}{1}".format(LOG, tmp_buffer)
    logpath = os.path.join(app.config['TMP_FOLDER'],
                           'flamenco-worker',
                           "{0}.log".format(task_id))
    f = open(logpath, 'a')
    f.write(tmp_buffer)
    f.close()
    return action

def _interactiveReadProcessWin(process, options):
    full_buffer = ''
    tmp_buffer = ''
    q = Queue.Queue()
    t_out = Thread(target=_checkOutputThreadWin, args=(process.stdout.fileno(), q,))
    t_err = Thread(target=_checkOutputThreadWin, args=(process.stderr.fileno(), q,))

    t_out.start()
    t_err.start()

    while True:
        tmp_buffer = _checkProcessOutputWin(process, q)
        if tmp_buffer:
            actions = _parse_output(tmp_buffer, options)
            if 'stop' in actions:
                update()
            pass
        if process.poll() is not None:
            break

    t_out.join()
    t_err.join()
    # full_buffer += _checkProcessOutputWin(process, q)
    return (process.returncode, full_buffer)

def _interactiveReadProcess(process, options):
    full_buffer = ''
    tmp_buffer = ''
    while True:
        tmp_buffer = _checkProcessOutput(process)

        if tmp_buffer:
            actions = _parse_output(tmp_buffer, options)
            print (actions)
            if 'stop' in actions:
                print ("UPDATE")
                update()
            pass
        if process.poll() is not None:
            break
    # It might be some data hanging around in the buffers after
    # the process finished
    # full_buffer += _checkProcessOutput(process)

    return (process.returncode, full_buffer)

def clear_dir(cleardir):
    if os.path.exists(cleardir):
        for root, dirs, files in os.walk(cleardir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))

def run_blender_in_thread(options):
    """We take the command and run it
    """
    global PROCESS
    global ACTIVITY
    global LOG
    global TIME_INIT
    global CONNECTIVITY

    render_command = json.loads(options['task_command'])

    workerstorage = os.path.join(app.config['TMP_FOLDER'], 'flamenco-worker')
    tmppath = os.path.join(
        workerstorage, str(options['job_id']))
    outpath = os.path.join(tmppath, 'output')
    clear_dir(outpath)
    jobpath = os.path.join(tmppath, str(options['job_id']), "")

    outputpath = os.path.join(
        workerstorage,
        str(options['job_id']),
        'output',
        str(options['task_id'])
    )

    dependpath = os.path.join(
        workerstorage,
        str(options['job_id']),
        'depend',
    )
    compiler_settings = options['compiler_settings']
    if 'command_name' in options['settings']:
        command_name = str(options['settings']['command_name'])
    else:
        # Backward compatibility
        command_name = "default"

    for cmd, val in enumerate(render_command):
        render_command[cmd] = render_command[cmd].replace(
            "==jobpath==",jobpath)
        render_command[cmd] = render_command[cmd].replace(
            "==outputpath==",outputpath)
        render_command[cmd] = render_command[cmd].replace(
            "==command==",
            compiler_settings['commands'][command_name][PLATFORM])

    os.environ['WORKER_DEPENDPATH'] = dependpath
    os.environ['WORKER_OUTPUTPATH'] = outputpath
    os.environ['WORKER_JOBPATH'] = jobpath

    print ( "Running:")
    for cmd in render_command:
        print (cmd)

    TIME_INIT = int(time.time())
    PROCESS = subprocess.Popen(render_command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

    # Make I/O non blocking for unix
    if platform.system() is not 'Windows':
        flags = fcntl(PROCESS.stdout, F_GETFL)
        fcntl(PROCESS.stdout, F_SETFL, flags | os.O_NONBLOCK)
        flags = fcntl(PROCESS.stderr, F_GETFL)
        fcntl(PROCESS.stderr, F_SETFL, flags | os.O_NONBLOCK)

    #flask.g.blender_process = process
    (retcode, full_output) =  _interactiveReadProcess(PROCESS, options) \
        if (platform.system() is not "Windows") \
        else _interactiveReadProcessWin(PROCESS, options)

    log = LOG
    activity = ACTIVITY
    time_init = TIME_INIT


    #flask.g.blender_process = None
    #print(full_output)
    script_dir = os.path.dirname(__file__)
    rel_path = 'render_log_' + HOSTNAME + '.log'
    abs_file_path = os.path.join(script_dir, rel_path)
    with open(abs_file_path, 'w') as f:
        f.write(full_output)

    if retcode == -9:
        status = 'canceled'
    elif retcode != 0:
        status = 'failed'
        if retcode == -11:
            segfault_text = "\nBlender Segmentation Fault\n"
            print (segfault_text)
            log += segfault_text
    else:
        status = 'completed'

    logging.debug(status)

    if time_init:
        time_cost = int(time.time())-time_init
    else:
        time_cost = 0
        logging.error("time_init is None")

    workerstorage = os.path.join(app.config['TMP_FOLDER'], 'flamenco-worker')
    taskpath = os.path.join(
        workerstorage,
        str(options['job_id']),
    )
    taskfile = os.path.join(
        taskpath,
        'taskfileout_{0}_{1}.zip'.format(options['job_id'], options['task_id'])
    )
    zippath = os.path.join(
        taskpath,
        'output',
        str(options['task_id']),
    )

    with ZipFile(taskfile, 'w') as taskzip:
        f = []
        for dirpath, dirnames, filenames in os.walk(zippath):
            for fname in filenames:
                filepath = os.path.join(dirpath, fname)
                taskzip.write(filepath, fname)

    tfiles = []
    no_storage = False
    workeroutputpath = os.path.join(
        taskpath,
        'output'
    )

    if 'storage' in compiler_settings and \
            'type' in compiler_settings['storage']:
        storage_settings = compiler_settings['storage']
        if storage_settings['type'] == 'filesystem':
            logging.info("Copying files via filesystem")
            # filesystem
            # path: Path to store files
            destination_path = "{0}/{1}".format(
                storage_settings['path'],
                options['job_id'])
            try:
                shutil.copytree(workeroutputpath, destination_path)
            except IOError:
                print ("Error storing output to Filesystem")
        elif storage_settings['type'] == 'ftp':
            # ftp
            # server: server domain (ftp.blender.org)
            # path: path on FTP server (/renders)
            # TODO test!
            server = storage_settings['server']
            path = storage_settings['path']
            from ftplib import FTP
            ftp = FTP(server)
            ftp.login()
            ftp.cwd(path)
            for dirpath, dirnames, filenames in os.walk(zippath):
                for fname in filenames:
                    filepath = os.path.join(dirpath, fname)
                    # TODO crossplataform?:
                    serverpath = os.path.join(path, str(options['job_id']))
                    file_ = open(filepath, 'rb')
                    ftp.storbinary('STOR '+str(fname), file_)
                    file_.close()
            ftp.quit()
        elif storage_settings['type'] == 'scp':
            # scp
            # server: server domain
            # user
            # password
            # path: path in server (if "system_keys" will use keys, must exist)
            # port
            from paramiko import SSHClient
            from paramiko import AutoAddPolicy
            from paramiko import ssh_exception
            from scp import SCPClient
            server = storage_settings['server']
            user = storage_settings['user']
            password = storage_settings['password']
            path = storage_settings['path']
            port = storage_settings.get('port')
            ssh = SSHClient()
            ssh.set_missing_host_key_policy(AutoAddPolicy())
            if password == 'system_keys':
                ssh.load_system_host_keys()
                try:
                    ssh.connect(server,
                                username=user,
                                port=port)
                except socket.error:
                    print ("Error uploading via SCP, socket error")
                except ssh_exception.SSHException:
                    print ("Error uploading via SCP, SSHException")
            else:
                try:
                    ssh.connect(server,
                                username=user,
                                password=password,
                                port=port)
                except socket.error:
                    print ("Error uploading via SCP, socket error")
                except ssh_exception.SSHException:
                    print ("Error uploading via SCP, SSHException")

            # TODO crossplataform?:
            filepath_remote = os.path.join(path,
                                            str(options['job_id']))
            with SCPClient(ssh.get_transport()) as scp:
                print ("Uploading via SCP")
                try:
                    scp.put(workeroutputpath,
                            filepath_remote,
                            recursive = True,
                            preserve_times = True)
                except scp.SCPException:
                    print ("Error uploading via SCP, SCPException")
            scp.close()
        else:
            no_storage = True
    else:
        no_storage = True

    if no_storage:
        tfiles = [
            ('taskfile', (
                'taskfile.zip', open(taskfile, 'rb'), 'application/zip'))]

    params = {
        'status': status,
        'log': log[-256:],
        'activity': activity,
        'time_cost': time_cost,
        'job_id': options['job_id'],
        }

    try:
        # Send results of the task to the server
        requests.patch(
            'http://{0}/tasks/{1}'.format(
                FLAMENCO_MANAGER, options['task_id']),
            data=params,
            files=tfiles,
        )
        CONNECTIVITY = True
    except ConnectionError:
        logging.error(
            'Cant connect with the Manager {0}'.format(FLAMENCO_MANAGER))
        CONNECTIVITY = False

    logging.debug( 'Return code: {0}'.format(retcode) )

    PROCESS = None
    ACTIVITY = None
    LOG = None
    TIME_INIT = None

def execute_task(task, files):
    global PROCESS
    #global LOCK

    if PROCESS:
        return "Error: Process failed", 500

    options = {
        'task_id': task['task_id'],
        'job_id': task['job_id'],
        'task_parser': task['task_parser'],
        'settings': task['settings'],
        'task_command': task['task_command'],
        'compiler_settings': task['compiler_settings'],
    }

    workerstorage = os.path.join(app.config['TMP_FOLDER'], 'flamenco-worker')
    taskpath = os.path.join(workerstorage, str(options['job_id']))
    zippath = os.path.join(taskpath, str(options['job_id']))

    options['jobpath'] = taskpath

    #LOCK.acquire()
    PROCESS = None
    LOG = None
    TIME_INIT = None
    ACTIVITY = None

    #render_thread = Thread(target=run_blender_in_thread, args=(options,))
    #render_thread.start()
    #render_thread.join()
    run_blender_in_thread(options)
    #LOCK.release()
    return json.dumps(dict(pid=0))

