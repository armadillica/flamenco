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
                          system=args['system'])
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
            workers[worker.hostname] = {
                "id" : worker.id,
                "hostname" : worker.hostname,
                "status" : worker.status,
                "activity" : worker.activity,
                "log" : worker.log,
                "time_cost" : worker.time_cost,
                "connection" : worker.connection,
                "system" : worker.system,
                "port" : worker.port,
                "ip_address" : worker.ip_address,
                "current_task" : worker.current_task}
        db.session.commit()
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

"""class WorkerLoopApi(Resource):
    def get(self):

        workers_query=Setting.query.filter_by(name='total_workers').first()
        if not workers_query:
            workers_query=Setting(
                name='total_workers',
                value=0)
            db.session.add(workers_query)
            db.session.commit()
            total_workers = 0
        else:
            total_workers = int(workers_query.value)

        count_workers = 0
        for worker in Worker.query.all():
            conn = worker.is_connected
            if conn and worker.status != 'disabled':
                worker.connection = 'online'
                db.session.add(worker)
                db.session.commit()
                # If is rendering, send info to server
                if worker.current_task and worker.status == 'rendering':
                    params = {
                        'id':worker.current_task,
                        'status':'running',
                        'log':worker.log,
                        'activity':worker.activity,
                        'time_cost':worker.time_cost }
                    try:
                        print ("Connecting to Server A")
                        http_request(app.config['BRENDER_SERVER'],
                            '/tasks', 'post', params=params)
                        print ("Clossing connection A")
                    except:
                        logging.warning('Error connecting to Server (Task not found?)')
                if worker.status in ['enabled', 'rendering']:
                    count_workers += 1

            if (not conn and worker.status != 'busy') or worker.status == 'disabled':
                if worker.current_task:
                    params = {
                        'id':worker.current_task,
                        'status':'failed',
                        'log':worker.log,
                        'activity':worker.activity,
                        'time_cost':worker.time_cost,
                    }
                    task = worker.current_task
                    if not conn:
                        worker.connection = 'offline'
                    worker.task = None
                    if worker.status == 'rendering':
                        worker.status = 'enabled'
                    db.session.add(worker)
                    db.session.commit()

                    try:
                        print ("Connecting to Server B")
                        http_request(app.config['BRENDER_SERVER'],
                            '/tasks', 'post', params=params)
                        print ("Clossing connection B")
                    except:
                        logging.error('Error connecting to Server (Task not found?)')
                    if worker.status == 'disabled' and task!=None:
                        try:
                            print ("Connecting to Server C")
                            http_request(app.config['BRENDER_SERVER'],
                                '/task/{0}'.format(), 'delete', params=params)
                            print ("Clossing connection C")
                        except:
                            logging.error('Error connecting to Server (Task not found?)')

        if total_workers != count_workers:
            total_workers = count_workers
            workers_query = Setting.query.filter_by(name='total_workers').first()
            workers_query.value = total_workers
            db.session.commit()

            uuid = Setting.query.filter_by(name='uuid').one()

            params = {'total_workers' : total_workers}

            # Update the resource on the server
            print ("Connecting to Server D")
            http_request( app.config['BRENDER_SERVER'],
                '/managers/{0}'.format(uuid.value), 'patch', params=params)
            print ("Clossing connection D")"""
