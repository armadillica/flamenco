import logging
from threading import Thread
from requests.exceptions import ConnectionError
from flask import jsonify
from flask import request
from flask import abort

from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from application import db
from application import app

from application.modules.workers.model import Worker
from application.helpers import http_request
from application.modules.settings.model import Setting

from datetime import datetime
from datetime import timedelta

parser = reqparse.RequestParser()
parser.add_argument('port', type=int)
parser.add_argument('hostname', type=str)
parser.add_argument('system', type=str)

status_parser = reqparse.RequestParser()
status_parser.add_argument("status", type=str)

worker_parser = reqparse.RequestParser()
worker_parser.add_argument("status", type=str)
worker_parser.add_argument("activity", type=str)
worker_parser.add_argument("log", type=str)
worker_parser.add_argument("time_cost", type=int)

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
                          current_task=None,
                          log=None,
                          time_cost=None,
                          activity=None,
                          connection='online',
                          system=args['system'][:20])
        else:
            worker.connection = 'online'
            worker.current_task = None

        db.session.add(worker)
        db.session.commit()

        return '', 204

    def get(self):
        workers={}
        workers_db = Worker.query.all()
        for worker in workers_db:
            timediff = None
            if worker.last_activity:
                timediff = datetime.now()-worker.last_activity
            if not timediff or timediff > timedelta(seconds=300):
                worker.connection = "offline"
                if worker.status != "disabled":
                    worker.status = "enabled"
                db.session.add(worker)
                db.session.commit()
            workers[worker.hostname] = {
                "id" : worker.id,
                "hostname" : worker.hostname,
                "status" : worker.status,
                "activity" : worker.activity,
                #"log" : worker.log,
                'log' : "",
                "time_cost" : worker.time_cost,
                "connection" : worker.connection,
                "system" : worker.system,
                "port" : worker.port,
                "ip_address" : worker.ip_address,
                "current_task" : worker.current_task}
        #db.session.commit()
        return jsonify(workers)


class WorkerStatusApi(Resource):
    def patch(self,worker_id):
        args = status_parser.parse_args()
        worker = Worker.query.get_or_404(worker_id)
        worker.status = args['status']
        db.session.add(worker)
        db.session.commit()

        return jsonify(dict(task_id = worker.current_task))


class WorkerApi(Resource):
    def patch(self, worker_id):
        args = worker_parser.parse_args()
        worker = Worker.query.get_or_404(worker_id)
        if worker.status != 'disabled':
            worker.status = args['status']
            worker.activity = args['activity']
            worker.log = args['log']
            worker.time_cost = args['time_cost']
            if args['status'] == 'disabled':
                worker.current_task = None
            db.session.add(worker)
            db.session.commit()
        return jsonify(dict(status=worker.status))

    def get(self, worker_id):
        worker = Worker.query.get_or_404(worker_id)
        try:
            worker_info = http_request(worker.host, '/run_info', 'get')
        except ConnectionError:
            worker_info = {'connection' : 'offline'}
        return worker_info

