from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask.ext.restful import marshal_with
from flask.ext.restful import fields

from flask import request

from werkzeug import secure_filename

from application import http_request
from application import db
from application import app
from application.modules.workers.model import Worker

import os
import json
import requests

import logging
from threading import Thread

parser = reqparse.RequestParser()
parser.add_argument('priority', type=int)
parser.add_argument('type', type=str)
parser.add_argument('task_id', type=int, required=True)
parser.add_argument('settings', type=str)
parser.add_argument('parser', type=str)

status_parser = reqparse.RequestParser()
status_parser.add_argument('status', type=str, required=True)
status_parser.add_argument('log', type=str)
status_parser.add_argument('activity', type=str)
status_parser.add_argument('time_cost', type=int)

parser_thumbnail = reqparse.RequestParser()
parser_thumbnail.add_argument("task_id", type=int)

task_fields = {
    'id' : fields.Integer,
    'worker_id' : fields.Integer,
    'priority' : fields.Integer,
    'frame_start' : fields.Integer,
    'frame_end' : fields.Integer,
    'frame_current' : fields.Integer,
    'status' : fields.String,
    'format' : fields.String
}

def get_availabe_worker():
    worker = Worker.query.filter_by(status='enabled', connection='online').first()
    if worker is None:
        return None
    elif not worker.is_connected:
        worker.connection = 'offline'

    db.session.add(worker)
    db.session.commit()
    return worker if worker.connection == 'online' else get_availabe_worker()

def schedule(task):
    logging.info("Scheduling")
    worker = get_availabe_worker()
    if worker is None:
        logging.debug("No worker available")
        return

    module_name = 'application.task_compilers.{0}'.format(task['type'])
    task_compiler = None
    try:
        module_loader = __import__(module_name, globals(), locals(), ['task_compiler'], 0)
        task_compiler = module_loader.task_compiler
    except ImportError, e:
        print('Error loading module {0}, {1}'.format(module_name, e))
        return

    task_command = task_compiler.compile(worker, task)

    if not task_command:
        logging.error('Cant compile {0}'.format(task['type']))
        return

    options = {
        'task_id' : task['task_id'],
        'task_parser' : task['parser'],
        'settings' : task['settings'],
        'task_command' : json.dumps(task_command)}

    #logging.info("send task %d" % task.server_id)
    pid = http_request(worker.host, '/execute_task', 'post', options)
    worker.status = 'rendering'
    worker.current_task = task['task_id']
    db.session.add(worker)
    db.session.commit()
    return True

class TaskManagementApi(Resource):
    @marshal_with(task_fields)
    def post(self):
        args = parser.parse_args()
        task={
            'priority' : args['priority'],
            'settings' : args['settings'],
            'task_id' : args['task_id'],
            'type' : args['type'],
            'parser' : args['parser'],
            }

        if not schedule(task):
            # Reject Task
            params = {
                'id': task['task_id'],
                'status':'ready',
                'time_cost':None,
                'log':None,
                'activity':None
            }
            request_thread = Thread(target=http_request, args=(app.config['BRENDER_SERVER'], '/tasks', 'post'), kwargs= {'params':params})
            request_thread.start()
            return '', 500


        return task, 202

class TaskApi(Resource):
    @marshal_with(task_fields)
    def delete(self, task_id):
        worker = Worker.query.filter_by(current_task = task_id).first()
        if worker:
            http_request(worker.host, '/kill', 'delete')
            worker.status = 'enabled'
            worker.current_task = None
            db.session.add(worker)
            db.session.commit()

        return task_id, 202

    def patch(self, task_id):
        args = status_parser.parse_args()
        worker = Worker.query.filter_by(current_task = task_id).first()
        if worker:
            worker.status = 'enabled'
            worker.current_task = None
            db.session.add(worker)
            db.session.commit()
        params = { 'id' : task_id, 'status': args['status'], 'time_cost' : args['time_cost'], 'log' : args['log'], 'activity' : args['activity'] }
        request_thread = Thread(target=http_request, args=(app.config['BRENDER_SERVER'], '/tasks', 'post'), kwargs= {'params':params})
        request_thread.start()

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
