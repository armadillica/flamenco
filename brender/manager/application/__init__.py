import os
import tempfile
import logging
import requests
from requests.exceptions import ConnectionError

from flask import Flask
from flask import jsonify
from flask import abort
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.restful import Api
from flask.ext.migrate import Migrate

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

from helpers import http_request

try:
    from application import config
    app.config['TMP_FOLDER']= config.Config.TMP_FOLDER
    app.config['THUMBNAIL_EXTENSIONS']= config.Config.THUMBNAIL_EXTENSIONS
    app.config.update(
        BRENDER_SERVER=config.Config.BRENDER_SERVER,
        SQLALCHEMY_DATABASE_URI= config.Config.SQLALCHEMY_DATABASE_URI,
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
            logging.error("The server {0} seems be unavailable.".format(app.config['BRENDER_SERVER']))
            exit(3)
        except KeyError:
            logging.error("Please, configure Brender Paths browsing Dashboard->Server->Settings")
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
    logging.error("No config.py file found, importing config from Server.")

    app.config['BRENDER_SERVER'] = 'localhost:9999'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(__file__), '../task_queue.sqlite')
    app.config['TMP_FOLDER'] = tempfile.gettempdir()
    app.config['THUMBNAIL_EXTENSIONS'] = set(['png'])

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
        logging.error("The server {0} seems be unavailable.".format(app.config['BRENDER_SERVER']))
        exit(3)
    except KeyError:
        logging.error("Please, configure Brender Paths browsing Dashboard->Server->Settings")
        exit(3)


api = Api(app)

from modules.tasks import TaskManagementApi
from modules.tasks import TaskApi
from modules.tasks import TaskThumbnailListApi
api.add_resource(TaskManagementApi, '/tasks')
api.add_resource(TaskApi, '/tasks/<int:task_id>')
api.add_resource(TaskThumbnailListApi, '/tasks/thumbnails')

from modules.workers import WorkerListApi
from modules.workers import WorkerApi
api.add_resource(WorkerListApi, '/workers')
api.add_resource(WorkerApi, '/workers/<int:worker_id>')

from modules.settings import SettingsListApi
from modules.settings import SettingApi
api.add_resource(SettingsListApi, '/settings')
api.add_resource(SettingApi, '/settings/<string:name>')

def register_manager(port, name, has_virtual_workers):
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
        'has_virtual_workers' : has_virtual_workers
        }

    r = http_request(app.config['BRENDER_SERVER'], '/managers', 'post', params=params)

    # Search in the settings if we have a uuid for the manager
    uuid = Setting.query.filter_by(name='uuid').first()
    # If we don't find one, we proceed to create it, using the server reponse
    if not uuid:
        uuid = Setting(name='uuid', value=r['uuid'])
        db.session.add(uuid)
        db.session.commit()
    # TODO: manage update if uuid already exists and does not match with the one
    # returned by the server


from application.modules.workers.model import Worker
from application.modules.settings.model import Setting

import threading

POOL_TIME = 5 #Seconds
worker_lock = threading.Lock()
worker_thread = threading.Thread()
total_workers = 0

def worker_loop_interrupt():
    global worker_thread
    worker_thread.cancel()


def worker_loop_function():
    global commonDataStruct
    global worker_thread
    global worker_lock
    global total_workers

    with worker_lock:
        # Count the currently available workers
        count_workers = 0
        for worker in Worker.query.all():
            conn = worker.is_connected
            if conn:
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
                        http_request(app.config['BRENDER_SERVER'], '/tasks', 'post', params=params)
                    except:
                        logging.warning('Error connecting to Server (Task not found?)')
                if worker.status in ['enabled', 'rendering'] and not worker.nimby:
                    count_workers += 1

            if not conn or worker.nimby:
                if worker.current_task:
                    # TODO remove log and time_cost
                    params = {
                        'id':worker.current_task,
                        'status':'failed',
                        'log':worker.log,
                        'activity':worker.activity,
                        'time_cost':worker.time_cost,
                    }

                    worker.connection = 'offline'
                    worker.task = None
                    worker.status = 'enabled'
                    db.session.add(worker)
                    db.session.commit()

                    try:
                        http_request(app.config['BRENDER_SERVER'], '/tasks', 'post', params=params)
                    except:
                        logging('Error connecting to Server (Task not found?)')

        if total_workers != count_workers:
            total_workers = count_workers
            # Get the manager uuid
            uuid = Setting.query.filter_by(name='uuid').one()

            params = {'total_workers' : total_workers}

            # Update the resource on the server
            http_request(
                app.config['BRENDER_SERVER'],
                '/managers/{0}'.format(uuid.value),
                'patch',
                params=params)


def worker_loop():
    global worker_thread
    try:
        worker_loop_function()
    except:
        logging.error('Exception in Worker Loop')
        pass
    worker_thread = threading.Timer(POOL_TIME, worker_loop, ())
    worker_thread.start()


@app.errorhandler(404)
def not_found(error):
    response = jsonify({'code' : 404, 'message' : 'No interface defined for URL'})
    response.status_code = 404
    return response
