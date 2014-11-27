from flask import jsonify
from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from application import db
from application.utils import list_integers_string
from application.modules.workers.model import Worker

parser = reqparse.RequestParser()
parser.add_argument("id", type=str)
parser.add_argument("status", type=str)

class WorkersListApi(Resource):
    def get(self):
        workers={}
        workers_db = Worker.query.all()
        for worker in workers_db:
            worker.connection = 'online' if worker.is_connected else 'offline'
            db.session.add(worker)

            workers[worker.hostname] = {"id": worker.id,
                                        "hostname": worker.hostname,
                                        "status": worker.status,
                                        "connection": worker.connection,
                                        "system": worker.system,
                                        "ip_address": worker.ip_address}
        db.session.commit()
        return jsonify(workers)


    def post(self):
        args = parser.parse_args()
        for worker_id in list_integers_string(args['id']):
            worker = Worker.query.get(worker_id)
            worker.status = args['status']
            db.session.add(worker)
        db.session.commit()

        return '', 204
