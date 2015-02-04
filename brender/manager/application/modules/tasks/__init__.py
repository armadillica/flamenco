from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask.ext.restful import marshal_with
from flask.ext.restful import fields

from flask import jsonify
from flask import abort
from flask import request

from werkzeug import secure_filename

from application import http_request
from application import db
from application import app
from application.modules.tasks.model import Task
from application.modules.workers.model import Worker

import os
import json
import requests

import logging
from threading import Thread

parser = reqparse.RequestParser()
parser.add_argument('priority', type=int)
# TODO add task_type informations
parser.add_argument('start', type=int, required=False)
parser.add_argument('end', type=int, required=False)
parser.add_argument('output_path_linux', type=str)
parser.add_argument('output_path_win', type=str)
parser.add_argument('output_path_osx', type=str)
parser.add_argument('format', type=str)
parser.add_argument('file_path_linux', type=str)
parser.add_argument('file_path_win', type=str)
parser.add_argument('file_path_osx', type=str)
parser.add_argument('task_id', type=int, required=True)
parser.add_argument('render_settings', type=str)

status_parser = reqparse.RequestParser()
status_parser.add_argument('status', type=str, required=True)

parser_thumbnail = reqparse.RequestParser()
parser_thumbnail.add_argument("task_id", type=int)

task_fields = {
    'id' : fields.Integer,
    #'task_type_id' : fields.Integer,
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

def schedule():
    logging.info("Scheduling")
    task_queue = Task.query.filter_by(status='ready').order_by(Task.priority.desc())
    for task in task_queue:
        worker = get_availabe_worker()
        if worker is None:
            logging.debug("No worker available")
            break
        task.status = 'running'

        if 'Darwin' in worker.system:
           setting_blender_path = app.config['BLENDER_PATH_OSX']
           setting_render_settings = app.config['SETTINGS_PATH_OSX']
           file_path = task.file_path_osx
           output_path = task.output_path_osx
        elif 'Windows' in worker.system:
           setting_blender_path = app.config['BLENDER_PATH_WIN']
           setting_render_settings = app.config['SETTINGS_PATH_WIN']
           file_path = task.file_path_win
           output_path = task.output_path_win
        else:
           setting_blender_path = app.config['BLENDER_PATH_LINUX']
           setting_render_settings = app.config['SETTINGS_PATH_LINUX']
           file_path = task.file_path_linux
           output_path = task.output_path_linux

        if setting_blender_path is None:
           print '[Debug] blender path is not set'

        blender_path = setting_blender_path

        if setting_render_settings is None:
           logging.warning("Render settings path not set!")

        render_settings = os.path.join(
           setting_render_settings,
            task.settings)

        #TODO the command will be in the database,
        #and not generated in the fly
        task_command = [
        str(blender_path),
        '--background',
        str(file_path),
        '--render-output',
        str(output_path),
        '--python',
        str(render_settings),
        '--frame-start' ,
        str(task.frame_current),
        '--frame-end',
        str(task.frame_end),
        '--render-format',
        str(task.format),
        '--render-anim',
        '--enable-autoexec'
        ]

        options = {
            'task_id' : task.id,
            'task_command' : json.dumps(task_command)}

        logging.info("send task %d" % task.server_id)
        pid = http_request(worker.host, '/execute_task', 'post', options)
        worker.status = 'busy'
        worker.current_task = task.id
        task.pid = int(pid['pid'])
        db.session.add(task)
        db.session.add(worker)
        db.session.commit()

class TaskManagementApi(Resource):
    @marshal_with(task_fields)
    def post(self):
        args = parser.parse_args()
        task = Task(
            server_id = args['task_id'],
            priority = args['priority'],
            frame_start = args['start'],
            frame_end = args['end'],
            frame_current = args['start'],
            output_path_linux = args['output_path_linux'],
            output_path_win = args['output_path_win'],
            output_path_osx = args['output_path_osx'],
            format = args['format'],
            file_path_linux = args['file_path_linux'],
            file_path_win = args['file_path_win'],
            file_path_osx = args['file_path_osx'],
            settings = args['render_settings'],
            status = 'ready'
        )

        db.session.add(task)
        db.session.commit()

        schedule()

        return task, 202

class TaskApi(Resource):
    @marshal_with(task_fields)
    def delete(self, task_id):
        task = Task.query.filter_by(server_id=task_id).first()
        if task is None:
            return '', 404
        db.session.delete(task)
        db.session.commit()

        if task.status not in ['finished', 'failed']:
            worker = Worker.query.filter_by(current_task = task.id).first()
            if worker:
                worker.status = 'enabled'
                worker.current_task = None
                db.session.add(worker)
                db.session.commit()
                task.status = 'aborted'
                http_request(worker.host, '/kill/' + str(task.pid), 'delete')

        schedule()

        return task, 202

    def patch(self, task_id):
        task = Task.query.get_or_404(task_id)
        args = status_parser.parse_args()

        task.status = args['status']
        db.session.commit()

        if task.status in ['finished', 'failed', 'aborted']:
            worker = Worker.query.filter_by(current_task = task.id).first()
            worker.status = 'enabled'
            worker.current_task = None
            db.session.add(worker)
            db.session.delete(task)
            db.session.commit()
            params = { 'id' : task.server_id, 'status' : task.status }
            request_thread = Thread(target=http_request, args=(app.config['BRENDER_SERVER'], '/tasks', 'post'), kwargs= {'params':params})
            request_thread.start()

        schedule()

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
        task = Task.query.get(args['task_id'])

        if not task:
            logging.info("Task {0} don't exist anymore".format(args['task_id']))
            return

        file = request.files['file']
        full_path = os.path.join(app.config['TMP_FOLDER'], file.filename)
        if file and self.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(full_path)

        params = dict(task_id=task.server_id)
        server_url = "http://%s/jobs/thumbnails" % (app.config['BRENDER_SERVER'])

        request_thread = Thread(target=self.send_thumbnail, args=(server_url, full_path, params))
        request_thread.start()