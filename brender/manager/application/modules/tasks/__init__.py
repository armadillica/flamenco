from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask.ext.restful import marshal_with
from flask.ext.restful import fields

from application import http_request
from application import db
from application.modules.tasks.model import Task
from application.modules.workers.model import Worker

parser = reqparse.RequestParser()
parser.add_argument('priority', type=int)
# TODO add task_type informations
parser.add_argument('frame_start', type=int, required=False)
parser.add_argument('frame_end', type=int, required=False)
parser.add_argument('frame_current', type=int, required=False)
parser.add_argument('output', type=str)
parser.add_argument('format', type=str)

status_parser = reqparse.RequestParser()
status_parser.add_argument('status', type=str, required=True)

task_fields = {
    'id' : fields.Integer,
    'task_type_id' : fields.Integer,
    'worker_id' : fields.Integer,
    'priority' : fields.Integer,
    'frame_start' : fields.Integer,
    'frame_end' : fields.Integer,
    'frame_current' : fields.Integer,
    'output' : fields.String,
    'status' : fields.String,
    'format' : fields.String
}

def get_availabe_worker():
    worker = Worker.query.filter_by(status='enabled', connection='online').first()
    if worker is None:
        return None
    else:
        worker.connection = 'offline'

    db.session.add(worker)
    db.session.commit()
    return worker if worker.connection == 'online' else get_availabe_worker()

def schedule():
    task_queue = Task.query.filter_by(status='ready').order_by(Task.priority.desc())
    for task in task_queue:
        worker = get_availabe_worker()
        if worker is None:
            break
        task.worker_id = worker.id
        task.status = 'running'
        options = {
            'task_id' : task.id,
            'file_path' : task.file_path,
            'blender_path' : app.config['BLENDER_PATH_LINUX'],
            'start_frame' : task.current_frame,
            'end_frame' : task.end_frame,
            'render_settings' : task.settings,
            'output' : task.output,
            'format' : task.format}
        http_request(worker.host, '/execute_task', 'post', data=options)
        db.session.add(task)
        db.session.commit()

class TaskManagementApi(Resource):
    @marshal_with(task_fields)
    def post(self):
        args = parser.parse_args()
        task = Task(
            priority = args['priority'],
            frame_start = args['frame_start'],
            frame_end = args['frame_end'],
            frame_current = args['frame_current'],
            output = args['output'],
            format = args['format'],
            status = 'ready'
        )

        db.session.add(task)
        db.session.commit()

        schedule()

        return task, 202

class TaskApi(Resource):
    @marshal_with(task_fields)
    def delete(self, task_id):
        task = Task.query.get_or_404(task_id)
        worker = Worker.query.get(task.worker_id)
        http_request(worker.host, '/kill/' + task.pid, 'delete')
        db.session.delete(task)

        if task.status not in ['completed', 'failed']:
            task.status = 'aborted'

        return task, 202

    def patch(self, task_id):
        task = db.query.get_or_404(task_id)
        args = status_parser.parse_args()

        task.status = args['status']

        if task.status in ['completed', 'failed']:
            http_request(BRENDER_SERVER, '/tasks', '/post', data=jsonify(task))
            db.session.delete(task)

        return '', 204
