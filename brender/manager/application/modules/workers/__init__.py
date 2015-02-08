import logging

from flask import jsonify
from flask import request

from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask import Flask, request, redirect, url_for

from application import app
from application import db

from application.modules.workers.model import Worker
from application.modules.settings.model import Setting
from application.helpers import http_request

parser = reqparse.RequestParser()
parser.add_argument('port', type=int)
parser.add_argument('hostname', type=str)
parser.add_argument('system', type=str)

status_parser = reqparse.RequestParser()
status_parser.add_argument("status", type=str)
status_parser.add_argument("activity", type=str)

class WorkerListApi(Resource):
    def post(self):
        args = parser.parse_args()
        ip_address = request.remote_addr
        port = args['port']

        worker = Worker.query.filter_by(ip_address=ip_address, port=port).first()
        if not worker:
            logging.info("New worker connecting from {0}".format(ip_address))
            worker = Worker(hostname=args['hostname'],
                          ip_address=ip_address,
                          port=port,
                          status='enabled',
                          log=None,
                          activity=None,
                          connection='online',
                          system=args['system'])
        else:
            worker.connection = 'online'

        db.session.add(worker)
        db.session.commit()

        return '', 204

    def get(self):
        workers={}
        workers_db = Worker.query.all()
        for worker in workers_db:

            workers[worker.hostname] = {"id": worker.id,
                                        "hostname": worker.hostname,
                                        "status": worker.status,
                                        "activity": worker.activity,
                                        "log": worker.log,
                                        "connection": worker.connection,
                                        "system": worker.system,
                                        "port" : worker.port,
                                        "ip_address": worker.ip_address,
                                        "current_task": worker.current_task}
        db.session.commit()
        return jsonify(workers)


class WorkerApi(Resource):
    def patch(self, worker_id):
        args = status_parser.parse_args()
        worker = Worker.query.get_or_404(worker_id)
        worker.status = args['status']
        worker.activity = args['activity']
        worker.log = args['log']
        db.session.add(worker)
        db.session.commit()
        return jsonify(dict(status=worker.status))

    def get(self, worker_id):
        worker = Worker.query.get_or_404(worker_id)
        return http_request(worker.host, '/run_info', 'get')
