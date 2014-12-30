from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask.ext.restful import marshal_with
from flask.ext.restful import fields

from flask import jsonify
from flask import abort

from application import http_request
from application import db
from application import app
from application.modules.tasks.model import Task
from application.modules.workers.model import Worker

from os.path import join

import logging

parser = reqparse.RequestParser()
parser.add_argument('priority', type=int)
# TODO add task_type informations
parser.add_argument('start', type=int, required=False)
parser.add_argument('end', type=int, required=False)
parser.add_argument('output', type=str)
parser.add_argument('format', type=str)
parser.add_argument('file_path_linux', type=str)
parser.add_argument('file_path_win', type=str)
parser.add_argument('file_path_osx', type=str)
parser.add_argument('task_id', type=int, required=True)
parser.add_argument('render_settings', type=str)

status_parser = reqparse.RequestParser()
status_parser.add_argument('status', type=str, required=True)

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
    worker = Worker.query.filter_by(status='enabled').filter_by(connection='online').first()
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
        task.worker_id = worker.id
        task.status = 'running'
        #TODO Select infos according to worker's system
        options = {
            'task_id' : task.id,
            'file_path' : task.file_path_linux,
            'blender_path' : app.config['BLENDER_PATH_LINUX'],
            'start' : task.frame_current,
            'end' : task.frame_end,
            'render_settings' : join(app.config['SETTINGS_PATH_LINUX'], task.settings),
            'output' : task.output,
            'format' : task.format}

        logging.info("send task %d" % task.server_id)
        pid = http_request(worker.host, '/execute_task', 'post', options)
        worker.status = 'busy'
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
            output = args['output'],
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
            abort(404)
        db.session.delete(task)
        db.session.commit()

        if task.status not in ['finished', 'failed']:
            worker = Worker.get(task.worker_id)
            worker.status = 'enabled'
            db.session.add(worker)
            db.session.commit()
            task.status = 'aborted'
            http_request(worker.host, '/kill/' + str(task.pid), 'delete')

        return task, 202

    def patch(self, task_id):
        task = Task.query.get_or_404(task_id)
        args = status_parser.parse_args()

        task.status = args['status']

        if task.status in ['finished', 'failed']:
            worker = Worker.query.get(task.worker_id)
            worker.status = 'enabled'
            db.session.add(worker)
            db.session.delete(task)
            db.session.commit()
            params = { 'id' : task.server_id, 'status' : task.status }
            http_request(app.config['BRENDER_SERVER'], '/tasks', 'post', params=params)

        return '', 204
