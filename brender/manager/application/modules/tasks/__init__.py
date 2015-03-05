from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask.ext.restful import marshal_with
from flask.ext.restful import fields

from flask import request
from flask import g
from flask import send_from_directory

from werkzeug.datastructures import FileStorage
from werkzeug import secure_filename

from zipfile import ZipFile

from application import http_request
from application import db
from application import app
from application.modules.workers.model import Worker

import os
import json
import requests

import logging
from threading import Thread

from requests.exceptions import ConnectionError


parser = reqparse.RequestParser()
parser.add_argument('priority', type=int)
parser.add_argument('type', type=str)
parser.add_argument('task_id', type=int, required=True)
parser.add_argument('job_id', type=int)
parser.add_argument('settings', type=str)
parser.add_argument('parser', type=str)
parser.add_argument('jobfile', type=FileStorage, location='files')

status_parser = reqparse.RequestParser()
status_parser.add_argument('status', type=str, required=True)
status_parser.add_argument('log', type=str)
status_parser.add_argument('activity', type=str)
status_parser.add_argument('time_cost', type=int)
status_parser.add_argument('job_id', type=int)
status_parser.add_argument('task_id', type=int)
status_parser.add_argument('taskfile', type=FileStorage, location='files')

parser_thumbnail = reqparse.RequestParser()
parser_thumbnail.add_argument("task_id", type=int)

task_fields = {
    'id': fields.Integer,
    'worker_id': fields.Integer,
    'priority': fields.Integer,
    'frame_start': fields.Integer,
    'frame_end': fields.Integer,
    'frame_current': fields.Integer,
    'status': fields.String,
    'format': fields.String
}

class TaskFileApi(Resource):
    def get(self, job_id):
        """Check if the Manager already have the file
        """
        managerstorage = app.config['MANAGER_STORAGE']
        jobpath = os.path.join(managerstorage, str(job_id))
        filepath = os.path.join(jobpath, "jobfile_{0}.zip".format(job_id))
        return {'file': os.path.isfile(filepath)}, 200


def add_file(bindata, name, job_id):
    managerstorage = app.config['MANAGER_STORAGE']
    jobpath = os.path.join(managerstorage, str(job_id), 'addfiles')
    if not os.path.exists(jobpath):
        os.mkdir(jobpath)

    file_path = os.path.join(jobpath, name)

    f = open(file_path,"w")
    f.write(bindata)
    f.close()
    return True


def get_availabe_worker():
    worker = Worker.query.filter_by(
        status='enabled', connection='online').first()
    if worker is None:
        return None
    return worker if worker.connection == 'online' else get_availabe_worker()

# /tasks/compiled/id
class TaskCompiledApi(Resource):
    def get(self, task_id):
        logging.info("Scheduling")
        #worker = get_availabe_worker()
        #if worker is None:
        #    logging.debug("No worker available")
        #    return

        #task = g.get("tasks", None)

        #tasks = http_request(app.config['BRENDER_SERVER'], '/tasks', 'get')

        ip_address = request.remote_addr
        worker = Worker.query.filter_by(ip_address=ip_address).one()
        if worker.status == "disabled":
            return '', 403

        tasks = TaskManagementApi().get()
        if not len(tasks[0]):
            return '', 400
        task = tasks[0]
        for t in task:
            task = task[t]
            task['task_id'] = t
            break
        #for t in tasks:
        #    task = tasks[t]
        #    break
        #for t in tasks:
        #    print (t)
        #task = tasks[task_id]

        managerstorage = app.config['MANAGER_STORAGE']
        jobpath = os.path.join(managerstorage, str(task['job_id']))
        if not os.path.exists(jobpath):
            os.mkdir(jobpath)


        # TODO make random name
        tmpfile = os.path.join(
            jobpath, 'jobfile_{0}.zip'.format(task['job_id']))

        lockfile = os.path.join(
            jobpath, 'jobfile_{0}.lock'.format(task['job_id']))

        if os.path.exists(lockfile):
            return '', 400

        if not os.path.exists(tmpfile):
            with open(lockfile, 'w') as f:
                f.write("locked")

            r = requests.get(
                'http://{0}/jobs/file/{1}'.format(
                    app.config['BRENDER_SERVER'], task['job_id'])
            )

            with open(tmpfile, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        f.flush()

            os.remove(lockfile)


        module_name = 'application.task_compilers.{0}'.format(task['type'])
        task_compiler = None
        try:
            module_loader = __import__(
                module_name, globals(), locals(), ['task_compiler'], 0)
            task_compiler = module_loader.task_compiler
        except ImportError, e:
            logging.error(' loading module {0}, {1}'.format(module_name, e))
            return

        worker = Worker.query.first()
        task_command = task_compiler.compile(worker, task, add_file)

        if not task_command:
            logging.error("Can't compile {0}".format(task['type']))
            return

        options = {
            'task_id': task['task_id'],
            'job_id': task['job_id'],
            'task_parser': task['parser'],
            'settings': task['settings'],
            'task_command': json.dumps(task_command)}

        r = requests.get(
            'http://{0}/jobs/file/output/{1}'.format(
                app.config['BRENDER_SERVER'], task['job_id'])
        )

        # TODO make random name
        tmpfile = os.path.join(
            app.config['TMP_FOLDER'], 'tmp_dep_{0}.zip'.format(task['task_id']))

        with open(tmpfile, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()

        jobfile = []
        jobfile.append(
            ('jobdepfile', (
                'jobdepfile.zip',
                open(tmpfile, 'rb'),
                'application/zip')
            )
        )

        pid = None
        if 1:
            managerstorage = app.config['MANAGER_STORAGE']
            jobpath = os.path.join(managerstorage, str(task['job_id']))
            zippath = os.path.join(
                jobpath, "jobfile_{0}.zip".format(task['job_id']))

            zipsuppath = None
            addpath = os.path.join(managerstorage, str(task['job_id']), 'addfiles')
            if os.path.exists(addpath):
                zipsuppath = os.path.join(
                    jobpath, "jobsupportfile_{0}.zip".format(task['job_id']))
                with ZipFile(zipsuppath, 'w') as jobzip:
                    f = []
                    for dirpath, dirnames, filenames in os.walk(addpath):
                        for fname in filenames:
                            filepath = os.path.join(dirpath, fname)
                            jobzip.write(filepath, fname)

            jobfile.append(
                ('jobfile', (
                    'jobfile.zip',
                    open(zippath, 'rb'),
                    'application/zip')
                )
            )
            if zipsuppath:
                jobfile.append(
                    ('jobsupportfile', (
                        'jobsupportfile.zip',
                        open(zipsuppath, 'rb'),
                        'application/zip')
                    ),
                )

        jflist = []
        for jf in jobfile:
            jflist.append([jf[0],jf[1][0]])


        worker.current_task = task['task_id']
        db.session.add(worker)
        db.session.commit()

        return {"options": options, "files": {"jobfiles":jflist}}, 200

        """worker.status = 'busy'
        worker.current_task = task['task_id']
        db.session.add(worker)
        db.session.commit()

        try:
            pid = http_request(
                worker.host, '/execute_task', 'post', options, files=jobfile)
        except ConnectionError, e:
            logging.error ("Connection Error: {0}".format(e))
            worker.status = 'enabled'
            worker.current_task = None
            db.session.add(worker)
            db.session.commit()
            return False

        if not u'pid' in pid:

            worker.status = 'enabled'
            worker.current_task = None
            db.session.add(worker)
            db.session.commit()
            return False

        worker.status = 'rendering'
        db.session.add(worker)
        db.session.commit()"""

        return True

class TaskManagementApi(Resource):
    @marshal_with(task_fields)
    def post(self):
        args = parser.parse_args()
        task={
            'priority' : args['priority'],
            'settings' : args['settings'],
            'task_id' : args['task_id'],
            'job_id':args['job_id'],
            'type' : args['type'],
            'parser' : args['parser'],
            }

        if args['jobfile']:
            managerstorage = app.config['MANAGER_STORAGE']
            jobpath = os.path.join(managerstorage, str(task['job_id']))
            try:
                os.mkdir(jobpath)
            except:
                pass
            args['jobfile'].save( os.path.join(jobpath, 'jobfile_{0}.zip'.format(task['job_id'])) )

        """if not schedule(task):
            # Reject Task
            params = {
                'id': task['task_id'],
                'status':'ready',
                'time_cost':None,
                'log':None,
                'activity':None
            }
            return '', 500"""

        return task, 202

    def get(self):
        r = http_request(app.config['BRENDER_SERVER'], '/tasks', 'get')
        g.tasks = r
        return r, 200

class TaskApi(Resource):
    @marshal_with(task_fields)
    def delete(self, task_id):
        worker = Worker.query.filter_by(current_task = task_id).first()
        if worker:
            if worker.status != 'disabled':
                worker.status = 'enabled'
            worker.current_task = None
            db.session.add(worker)
            db.session.commit()

        return task_id, 202

    def patch(self, task_id):
        args = status_parser.parse_args()
        ip_address = request.remote_addr
        worker = Worker.query.filter_by(ip_address=ip_address).first()
        if not worker:
            return 'Worker is not registered', 403
        if worker.status=='disabled':
            return 'Worker is Disabled', 403
        if not worker.current_task:
            return 'Task Cancelled', 403
        if worker:
            if args['status'] == 'enabled':
                worker.current_task = None
            elif args['status'] == 'rendering':
                worker.current_task = args['task_id']
            db.session.add(worker)
            db.session.commit()

        """if args['task_id']:
            task = Task.query.filter_by(id=args['task_id']).first()
            if not task:
                return 'Task is cancelled', 403"""

        if args['taskfile']:
            managerstorage = app.config['MANAGER_STORAGE']
            jobpath = os.path.join(managerstorage, str(args['job_id']))
            try:
                os.mkdir(jobpath)
            except:
                pass
            zippath = os.path.join(
                    jobpath,
                    'taskfileout_{0}_{1}.zip'.format(args['job_id'], task_id))
            args['taskfile'].save(zippath)

        jobfile=None
        if args['taskfile']:
            jobfile = [
                ('taskfile', (
                    'taskfile.zip', open(zippath, 'rb'), 'application/zip'))]

        params = { 'id' : task_id, 'status': args['status'], 'time_cost' : args['time_cost'], 'log' : args['log'], 'activity' : args['activity'] }
        http_request(app.config['BRENDER_SERVER'], '/tasks', 'post', params=params, files=jobfile)

        return '', 204

class TaskThumbnailListApi(Resource):
    """Thumbnail list interface for the Manager
    """

    def send_thumbnail(self, server_url, file_path, params):
            thumbnail_file = open(file_path, 'r')
            requests.post(server_url, files={'file': thumbnail_file}, data=params)
            thumbnail_file.close()

    def allowed_file(self, filename):
        """Filter extensions acording to THUMBNAIL_EXTENSIONS configuration.
        """
        return '.' in filename and \
               filename.rsplit('.', 1)[1] in app.config['THUMBNAIL_EXTENSIONS']

    def post(self):
        """Accepts a thumbnail file and a task_id (worker task_id),
        and send it to the Server with the task_id (server task_id).
        """

        args = parser_thumbnail.parse_args()

        file = request.files['file']
        full_path = os.path.join(app.config['TMP_FOLDER'], file.filename)
        if file and self.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(full_path)

        params = dict(task_id=args['task_id'])
        server_url = "http://%s/jobs/thumbnails" % (app.config['BRENDER_SERVER'])

        request_thread = Thread(target=self.send_thumbnail, args=(server_url, full_path, params))
        request_thread.start()



class TaskZipApi(Resource):
    def get(self, job_id):
        """Given a job_id returns the task file
        """
        managerstorage = app.config['MANAGER_STORAGE']
        jobpath = os.path.join(managerstorage, str(job_id))
        return send_from_directory(
            jobpath, 'jobfile_{0}.zip'.format(job_id))


class TaskSupZipApi(Resource):
    def get(self, job_id):
        """Given a job_id returns the support file
        """
        managerstorage = app.config['MANAGER_STORAGE']
        jobpath = os.path.join(managerstorage, str(job_id))
        return send_from_directory(
            jobpath, 'jobsupportfile_{0}.zip'.format(job_id))


class TaskDepZipApi(Resource):
    def get(self, job_id):
        """Given a job_id returns the dep file
        """
        managerstorage = app.config['MANAGER_STORAGE']
        jobpath = os.path.join(managerstorage, str(job_id))
        return send_from_directory(
            jobpath, 'jobdepfile_{0}.zip'.format(job_id))
