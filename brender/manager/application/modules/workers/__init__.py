import os
import logging
import requests

from flask import jsonify
from flask import request

from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask import Flask, request, redirect, url_for
from werkzeug import secure_filename

from application import app
from application import db

from application.modules.workers.model import Worker
from application.modules.settings.model import Setting
from application.modules.tasks.model import Task
from application.helpers import http_request


parser = reqparse.RequestParser()
parser.add_argument('port', type=int)
parser.add_argument('hostname', type=str)
parser.add_argument('system', type=str)

status_parser = reqparse.RequestParser()
status_parser.add_argument("status", type=str)

parser_thumbnail = reqparse.RequestParser()
parser_thumbnail.add_argument("task_id", type=int)

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
            worker.connection = 'online' if worker.is_connected else 'offline'
            db.session.add(worker)

            workers[worker.hostname] = {"id": worker.id,
                                        "hostname": worker.hostname,
                                        "status": worker.status,
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
        db.session.add(worker)
        db.session.commit()
        return jsonify(dict(status=worker.status))

    def get(self, worker_id):
        worker = Worker.query.get_or_404(worker_id)
        return http_request(worker.host, '/run_info', 'get')

class ThumbnailListApi(Resource):
    """
    Thumbnail list interface for the Manager
    """

    def allowed_file(self, filename):
        """
        Filter extensions acording to THUMBNAIL_EXTENSIONS configuration.
        """
        return '.' in filename and \
               filename.rsplit('.', 1)[1] in app.config['THUMBNAIL_EXTENSIONS']

    def post(self):
        """
        Accepts a thumbnail file and a task_id (worker task_id),
        and send it to the Server with the task_id (server task_id).
        """
        args = parser_thumbnail.parse_args()
        task = Task.query.get(args['task_id'])
        file = request.files['file']
        full_path = os.path.join(app.config['TMP_FOLDER'], file.filename)
        if file and self.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(full_path)

        params = dict(task_id=task.server_id)

        thumbnail_file = open(full_path, 'r')
        server_url = "http://%s/thumbnails" % (app.config['BRENDER_SERVER'])
        r = requests.post(server_url, files={'file': thumbnail_file}, data=params)
        thumbnail_file.close()