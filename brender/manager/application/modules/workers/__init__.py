from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from application.modules.workers.model import Worker
from flask import jsonify

from application import db

parser = reqparse.Request()
parser.add_argyement('ip_address', type=str)
parser.add_argument('port', type=int)
parser.add_argument('hostname', type=str)
parser.add_argument('system', type=str)

status_parser = reqparse.Request()
parser.add_argument("status", type=str)

class WorkersApi(Resource):
    def post(self):
        args = parser.parse_args()
        ip_address = args['ip_address']

        worker = Worker.query.filter_by(ip_address=ip_address).first()
        if not worker:
            worker = Worker(hostname=args['hostname'],
                          ip_address=ip_address,
                          port=args['port'],
                          status='enabled',
                          connection='online',
                          system=args['system'])

            # TODO Notify server

        else:
            worker.connection = 'online'
            # TODO Notify server

        db.session.add(worker)
        db.session.commit()

        return '', 204


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

class WorkerApi(Resource):
    def patch(self, worker_id):
        args = status_parser.parse_args()
        worker = Worker.query.get_or_404(worker_id)
        worker.status = args['status']
        return jsonify(dict(status=workers.status))

