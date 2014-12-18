from flask import Flask
from flask import jsonify
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.restful import Api
from flask.ext.migrate import Migrate
import requests
import os

import logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

try:
    import config
    app.config.from_object(config.Manager)
except:
    app.config.update(
        DEGUG=False,
        HOST='localhost',
        PORT=7777,
        SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(os.path.dirname(__file__), '../task_queue.sqlite'),
        BLENDER_PATH_OSX = "",
        BLENDER_PATH_LINUX = "",
        BLENDER_PATH_WIN = ""
    )

api = Api(app)

def http_request(ip_address, command, method, params=None):
    if method == 'delete':
        r = requests.get('http://' + ip_address + commmand)
    elif method == 'post':
        r = requests.post('http://' + ip_address + command, data=params)
    elif method == 'get':
        r = requests.get('http://' + ip_address + command)
    elif method == 'put':
        r = requests.put('http://' + ip_address + command, data=params)
    elif method == 'patch':
        r = requests.patch('http://' + ip_address + command, data=params)

    if r.status_code == 404:
        return abort(404)

    if r.status_code == 204:
        return '', 204

    return r.json()


from modules.tasks import TaskManagementApi
from modules.tasks import TaskApi
api.add_resource(TaskManagementApi, '/tasks')
api.add_resource(TaskApi, '/tasks/<int:task_id>')

from modules.workers import WorkerListApi
from modules.workers import WorkerApi
api.add_resource(WorkerListApi, '/workers')
api.add_resource(WorkerApi, '/workers/<int:worker_id>')

@app.errorhandler(404)
def not_found(error):
    response = jsonify({'code' : 404, 'message' : 'No interface defined for URL'})
    response.status_code = 404
    return response
