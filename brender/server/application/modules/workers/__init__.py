import os
import json
import requests
from flask import Flask
from flask import jsonify
from flask import request
from flask import redirect
from flask import Response
from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from werkzeug import secure_filename
from application import db
from application import app
from application.utils import list_integers_string
from application.utils import http_rest_request
from application.modules.workers.model import Worker
from application.modules.managers.model import Manager
from application.modules.tasks.model import Task

parser = reqparse.RequestParser()
parser.add_argument("id", type=str)
parser.add_argument("status", type=str)

parser_thumbnail = reqparse.RequestParser()
parser_thumbnail.add_argument("task_id", type=int)

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


class ThumbnailListApi(Resource):
    """
    Thumbnail list interface for the Server
    """
    def allowed_file(self, filename):
        """
        Filter extensions acording to THUMBNAIL_EXTENSIONS configuration.
        """
        return '.' in filename and \
               filename.rsplit('.', 1)[1] in app.config['THUMBNAIL_EXTENSIONS']

    def post(self):
        """
        Accepts a thumbnail file and a task_id and stores it.
        """
        args = parser_thumbnail.parse_args()
        task = Task.query.get(args['task_id'])
        thumbnail_filename = "thumbnail_%s.png" % task.job_id
        file = request.files['file']
        if file and self.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join( app.config['TMP_FOLDER'] , thumbnail_filename))


class ThumbnailApi(Resource):
    """
    Thumbnail interface for the Server
    """
    def get(self, job_id):
        """
        Returns the last thumbnail for the Job, or a blank
        image if none.
        """
        def generate():
            file_path = os.path.join(app.config['TMP_FOLDER'],'thumbnail_%s.png' % job_id)
            print (file_path)
            if os.path.isfile(file_path):
                thumb_file = open(str(file_path), 'r')
                return thumb_file.read()
            else:
                with app.open_resource('static/missing_thumbnail.png') as thumb_file:
                    return thumb_file.read()
            return False
        bin = generate()
        if bin:
            return Response(bin, mimetype='image/png')
        else:
            return '',404
