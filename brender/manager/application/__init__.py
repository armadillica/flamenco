import os
import logging

from flask import Flask
from flask import jsonify
from flask import abort
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.restful import Api
from flask.ext.migrate import Migrate

from requests.exceptions import ConnectionError

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
db = SQLAlchemy(app)
migrate = Migrate(app, db)


from helpers import http_request

try:
    from application import config
    app.config.update(
        BRENDER_SERVER=config.Config.BRENDER_SERVER,
        SQLALCHEMY_DATABASE_URI= config.Config.SQLALCHEMY_DATABASE_URI
    )

    if not config.Config.IS_PRIVATE_MANAGER:
        try:
            server_settings = http_request(app.config['BRENDER_SERVER'], '/settings', 'get')
            app.config.update(
                BLENDER_PATH_LINUX=server_settings['blender_path_linux'],
                BLENDER_PATH_OSX=server_settings['blender_path_osx'],
                BLENDER_PATH_WIN=server_settings['blender_path_win'],
                SETTINGS_PATH_LINUX=server_settings['render_settings_path_linux'],
                SETTINGS_PATH_OSX=server_settings['render_settings_path_osx'],
                SETTINGS_PATH_WIN=server_settings['render_settings_path_win']
            )
        except ConnectionError:
            logging.info("The server {0} seems be unavailable.".format(app.config['BRENDER_SERVER']))
            exit(3)
    else:
        app.config.update(
            BLENDER_PATH_LINUX=config.Config.BLENDER_PATH_LINUX,
            BLENDER_PATH_OSX=config.Config.BLENDER_PATH_OSX,
            BLENDER_PATH_WIN=config.Config.BLENDER_PATH_WIN,
            SETTINGS_PATH_LINUX=config.Config.SETTINGS_PATH_LINUX,
            SETTINGS_PATH_OSX=config.Config.SETTINGS_PATH_OSX,
            SETTINGS_PATH_WIN=config.Config.SETTINGS_PATH_WIN
        )

except ImportError:
    """If a config is not defined, we use the default settings, importing the
    BLENDER_PATH and SETTINGS_PATH from the server.
    """

    app.config['BRENDER_SERVER'] = 'localhost:9999'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(__file__), '../task_queue.sqlite')

    try:
        server_settings = http_request(app.config['BRENDER_SERVER'], '/settings', 'get')
        app.config.update(
            BLENDER_PATH_LINUX=server_settings['blender_path_linux'],
            BLENDER_PATH_OSX=server_settings['blender_path_osx'],
            BLENDER_PATH_WIN=server_settings['blender_path_win'],
            SETTINGS_PATH_LINUX=server_settings['render_settings_path_linux'],
            SETTINGS_PATH_OSX=server_settings['render_settings_path_osx'],
            SETTINGS_PATH_WIN=server_settings['render_settings_path_win']
        )
    except ConnectionError:
        logging.info("The server {0} seems be unavailable.".format(app.config['BRENDER_SERVER']))
        exit(3)


api = Api(app)

from modules.tasks import TaskManagementApi
from modules.tasks import TaskApi
api.add_resource(TaskManagementApi, '/tasks')
api.add_resource(TaskApi, '/tasks/<int:task_id>')

from modules.workers import WorkerListApi
from modules.workers import WorkerApi
api.add_resource(WorkerListApi, '/workers')
api.add_resource(WorkerApi, '/workers/<int:worker_id>')


def register_manager(port, name, total_workers):
    """This is going to be an HTTP request to the server with all the info for
    registering the render node. This is called by the runserver script.
    """
    import httplib
    while True:
        try:
            connection = httplib.HTTPConnection(app.config['BRENDER_SERVER'])
            connection.request("GET", "/managers")
            break
        except socket.error:
            pass
        time.sleep(0.1)

    params = {
        'port' : port,
        'name' : name,
        'workers' : total_workers
        }
    http_request(app.config['BRENDER_SERVER'], '/managers', 'post', params=params)


@app.errorhandler(404)
def not_found(error):
    response = jsonify({'code' : 404, 'message' : 'No interface defined for URL'})
    response.status_code = 404
    return response
