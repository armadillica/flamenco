import json
import requests
from flask import jsonify
from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from application import db
from application import app
from application.utils import list_integers_string
from application.utils import http_rest_request
from application.modules.workers.model import Worker
from application.modules.managers.model import Manager

parser = reqparse.RequestParser()
parser.add_argument("id", type=str)
parser.add_argument("status", type=str)

class WorkerListApi(Resource):
    def get(self):
        workers={}
        for manager in Manager.query.all():
            try:
                r = http_rest_request(manager.host, '/workers', 'get')
                workers = dict(workers.items() + r.items())
            except:
                # TODO add proper exception handling!
                pass
        return jsonify(workers)

    # FIXME How to get the manager from the worker
    def post(self):
        args = parser.parse_args()
        for worker_id in list_integers_string(args['id']):
            worker = Worker.query.get(worker_id)
            worker.status = args['status']
            http_rest_request(worker.manager.host, '/workers/' + worker_id, 'patch', dict(status=worker.status))

        return '', 204

# FIXME this will probably be depreceated
class WorkerApi(Resource):
    def get(self, worker_id):
        worker = Worker.query.get_or_404(worker_id)
        r = requests.get('http://' + worker.ip_address + '/run_info')
        return r.json()

