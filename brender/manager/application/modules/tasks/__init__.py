from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask.ext.restful import marshal_with
from flask.ext.restful import fields

parser = reqparse.RequestParser()
parser.add_argument('priority', type=int)
# FIXME WHAT ABOUT TASK TYPE???
parser.add_argument('frame_start', type=int, required=False)
parser.add_argument('frame_end', type=int, required=False)
parser.add_argument('frame_current', type=int, required=False)

status_parser = reqparse.RequestParser()
status_parser.add_argument('status', type=str, required=True)

task_fields = {
    'id' = fields.Integer,
    'task_type_id' = fields.Integer,
    'worker_id' = fields.Integer,
    'priority' = fields.Integer,
    'frame_start' = fields.Integer,
    'frame_end' = fields.Integer,
    'frame_current' = fields.Integer,
    'status' = fields.String
}

def schedule():
    pass

class TaskManagementApi(Resource):
    @marshal_with(task_fields)
    def post(self):
        args = parser.parse_args()
        task = Task(
            priority = args['priority'],
            frame_start = args['frame_start'],
            frame_end = args['frame_end'],
            frame_current = args['frame_current'],
            status = 'running'
        )

        db.session.add(task)
        db.session.commit()

        schedule()

        return task, 202

class TaskApi(Resource):
    @marshal_with(task_fields)
    def delete(self, task_id):
        task = db.query.get_or_404(task_id)
        db.session.delete(task)

        # TODO Kill process

        if task.status not in ['completed', 'failed']:
            task.status = 'aborted'

        return task, 202

    def patch(self, task_id):
        task = db.query.get_or_404(task_id)
        args = status_parser.parse_args()

        task.status = args['status']

        if task.status in ['completed', 'failed']:
            db.session.delete(task)
            # TODO Update on server

        return '', 204
