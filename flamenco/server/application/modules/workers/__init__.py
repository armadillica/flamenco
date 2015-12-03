import requests
import logging
from flask import jsonify
from flask import abort
from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from application.utils import list_integers_string
from application.utils import http_rest_request
from application.utils import FlamencoManager
from application.modules.managers.model import Manager

parser = reqparse.RequestParser()
parser.add_argument("id", type=str)
parser.add_argument("status", type=str)


class WorkerListApi(Resource):
    def get(self):
        workers = {}
        for manager in Manager.query.all():
            if manager.has_virtual_workers:
                continue
            try:
                m = FlamencoManager(manager.host)
                r = m.get('workers')
                for worker in r.keys():
                    r[worker]['manager_id'] = manager.id
                workers = dict(workers.items() + r.items())
            except Exception, e:
                # TODO add proper exception handling!
                logging.error(e)
                pass
        return jsonify(workers)

    # FIXME How to get the manager from the worker
    def post(self):
        args = parser.parse_args()
        workers = []
        pairs = args['id'].split(',')
        for par in pairs:
            int_list = par.split(';')
            workers.append( map(int, int_list) )

        for worker_id, manager_id in workers:
            manager = Manager.query.get(manager_id)
            if not manager.has_virtual_workers:
                r = http_rest_request(
                    manager.host,
                    '/workers/status/{0}'.format(worker_id),
                    'patch', dict(status=args['status']))

        return '', 204


# FIXME this will probably be depreceated, because worker talk to the server
# only via the manager.
class WorkerApi(Resource):
    def get(self, worker_id):
        return abort(404)
        worker = Worker.query.get_or_404(worker_id)
        r = requests.get('http://' + worker.ip_address + '/run_info')
        return r.json()
