import os
import json
import requests
import logging
from threading import Thread
from datetime import datetime
from zipfile import ZipFile
from requests.exceptions import ConnectionError

from flask import request
from flask import send_from_directory
from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask.ext.restful import marshal_with
from flask.ext.restful import fields
from werkzeug.datastructures import FileStorage
from werkzeug import secure_filename

from application import http_request
from application import db
from application import app

from application.helpers import join_url_params
from application.modules.workers.model import Worker
from application.modules.settings.model import Setting


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
parser_thumbnail.add_argument('task_id', type=int)

parser_delete = reqparse.RequestParser()
parser_delete.add_argument('tasks', type=str, action='append', required=True)

task_management_parser = reqparse.RequestParser()
task_management_parser.add_argument('worker', type=str)

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


class TaskCompiledApi(Resource):
    def get(self, task_id):
        """Entry point for a worker to require a task, which will be compiled
        on the fly according to the worker specs.
        """
        logging.debug("Scheduling")

        # TODO we will need to make this more robust, and give each worker a uuid
        ip_address = request.remote_addr
        worker = Worker.query.filter_by(ip_address=ip_address).one()
        if not worker:
            logging.debug("Worker is not registered")
            return 'Worker is not registered', 403
        worker.last_activity = datetime.now()
        db.session.commit()
        if worker.status == 'disabled':
            logging.debug("Worker is disabled")
            return 'Worker is disabled', 403
        worker.current_task = None
        worker.status = 'enabled'
        db.session.commit()

        tasks = TaskManagementApi().get(job_types=",".join(worker.job_types_list))
        if tasks[0] == ('', 404):
            return '', 400
        if not len(tasks) or not len(tasks[0]):
            return '', 400
        task = tasks[0]

        worker.current_task = task['id']
        worker.child_task = task['child_id']
        db.session.commit()

        managerstorage = app.config['MANAGER_STORAGE']
        jobpath = os.path.join(managerstorage, str(task['job_id']))
        if not os.path.exists(jobpath):
            os.mkdir(jobpath)


        # TODO make random name
        tmpfile = os.path.join(
            jobpath, 'jobfile_{0}.zip'.format(task['job_id']))

        lockfile = os.path.join(
            jobpath, 'jobfile_{0}.lock'.format(task['job_id']))

        if os.path.isfile(lockfile):
            # Try and set the task back to wating
            params = dict(id=task_id, status='waiting')
            r = http_request(
                app.config['FLAMENCO_SERVER'],
                '/tasks/{0}'.format(task_id),
                'put',
                params=params)
            return '', 400

        zipok = True
        try:
            with ZipFile(tmpfile, 'r') as jobzip:
                jobzip.namelist()
        except:
            zipok = False

        if not os.path.isfile(tmpfile) or not zipok:
            with open(lockfile, 'w') as f:
                f.write("locked")

            r = requests.get(
                'http://{0}/jobs/file/{2}'.format(
                #'http://{0}/static/storage/{1}/{2}/jobfile_{2}.zip'.format(
                    app.config['FLAMENCO_SERVER'], task['project_id'], task['job_id']),
                stream=True
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

        task_command = task_compiler.compile(worker, task, add_file)

        if not task_command:
            logging.error("Can't compile {0}".format(task['type']))
            return

        options = {
            'task_id': task['id'],
            'job_id': task['job_id'],
            'task_parser': task['parser'],
            'settings': task['settings'],
            'type': task['type'],
            'task_command': json.dumps(task_command)}

        jobfile = []

        pid = None
        managerstorage = app.config['MANAGER_STORAGE']
        jobpath = os.path.join(managerstorage, str(task['job_id']))
        zippath = os.path.join(
            jobpath, "jobfile_{0}.zip".format(task['job_id']))

        jobfile.append(
            ('jobfile', (
                'jobfile.zip',
                open(zippath, 'rb'),
                'application/zip')
            )
        )

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


        return {"options": options, "files": {"jobfiles": jflist}}, 200


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
                'status':'waiting',
                'time_cost':None,
                'log':None,
                'activity':None
            }
            return '', 500"""

        return task, 202

    def get(self, job_types=None):
        # TODO: stop referring to job_types using the name and start using a UUID
        # Get the worker UUID as identification for asking tasks
        uuid = Setting.query.filter_by(name='uuid').first()
        # Currently this is implemented as a GET, with the uuid argument optional.
        # In the future the uuid will be sent in the headers.

        args = task_management_parser.parse_args()
        worker = args['worker']

        task_generate_params = {'uuid': uuid.value}
        if job_types and job_types != "":
            task_generate_params['job_types'] = job_types
        if worker:
            task_generate_params['worker'] = worker

        joined_tasks_generate_url = join_url_params(
            '/tasks/generate', task_generate_params)

        r = http_request(
            app.config['FLAMENCO_SERVER'], joined_tasks_generate_url,
            'get')

        return r, 200

    #@marshal_with(task_fields)
    def delete(self):
        args = parser_delete.parse_args()
        for task_id in args['tasks']:
            worker = Worker.query.filter_by(current_task=task_id).first()
            if worker:
                if worker.status != 'disabled':
                    worker.status = 'enabled'
                worker.current_task = None
                db.session.add(worker)
                db.session.commit()

        return task_id, 202


class TaskApi(Resource):

    def patch(self, task_id):
        """Send updates to the server regarding the status of a task.
        TODO: update the function to be a PUT, it is more consistent and also
        follows the server"""
        args = status_parser.parse_args()
        ip_address = request.remote_addr
        worker = Worker.query.filter_by(ip_address=ip_address).first()
        if not worker:
            return 'Worker is not registered', 403
        worker.last_activity = datetime.now()
        db.session.add(worker)
        db.session.commit()
        if worker.status == 'disabled':
            return 'Worker is disabled', 403
        if not worker.current_task:
            return 'Task cancelled', 403

        # If other workers are rendering the same task kill them
        others = Worker.query.filter(
            Worker.status == 'enabled',
            Worker.connection == 'online',
            Worker.id != worker.id,
            Worker.current_task == worker.current_task).count()

        if others > 0:
            return 'Duplicated task', 403

        """for other in others:
            other.current_task = None
            db.session.add(other)
            db.session.commit()"""

        if args['status'] == 'active':
            if args['task_id']:
                worker.current_task = args['task_id']
            worker.time_cost = args['time_cost']
            worker.log = args['log']
            worker.activity = args['activity']
            worker.status = 'rendering'
        else:
            worker.current_task = None
            worker.status = 'enabled'
        db.session.add(worker)
        db.session.commit()

        """if args['task_id']:
            task = Task.query.filter_by(id=args['task_id']).first()
            if not task:
                return 'Task is cancelled', 403"""

        jobfile = None
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

            # Store dependencies
            if worker.child_task:
                deppath = os.path.join(
                    jobpath, 'dependencies_{0}'.format(worker.child_task))
                if not os.path.exists(deppath):
                    os.mkdir(deppath)
                with ZipFile(zippath, 'r') as jobzip:
                    jobzip.extractall(path=deppath)

                depzippath = os.path.join(
                    jobpath, 'dependencies_{0}.zip'.format(worker.child_task))
                with ZipFile(depzippath, 'w') as depzip:
                    f = []
                    for dirpath, dirnames, filenames in os.walk(deppath):
                        for fname in filenames:
                            filepath = os.path.join(dirpath, fname)
                            depzip.write(filepath, fname)

            # Send to server
            jobfile = [
                ('taskfile', (
                    'taskfile.zip', open(zippath, 'rb'), 'application/zip'))]

        params = {
            'id': task_id,
            'status': args['status'],
            'time_cost': args['time_cost'],
            'log': args['log'], # we the trimmed version of the log
            'activity': args['activity']}

        r = http_request(
            app.config['FLAMENCO_SERVER'],
            '/tasks/{0}'.format(task_id),
            'put',
            params=params,
            files=jobfile)

        if r[1] == 403:
            return '', 403

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
        server_url = "http://%s/jobs/thumbnails" % (app.config['FLAMENCO_SERVER'])

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
