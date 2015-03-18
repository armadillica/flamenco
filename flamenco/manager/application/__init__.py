import os
import sys
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
from application.modules.settings.model import Setting

try:
    from application import config
    app.config['TMP_FOLDER']= config.Config.TMP_FOLDER
    app.config['THUMBNAIL_EXTENSIONS']= config.Config.THUMBNAIL_EXTENSIONS
    app.config['MANAGER_STORAGE'] = config.Config.MANAGER_STORAGE
    app.config.update(
        BRENDER_SERVER=config.Config.BRENDER_SERVER,
        SQLALCHEMY_DATABASE_URI= config.Config.SQLALCHEMY_DATABASE_URI,
    )

    if not config.Config.IS_PRIVATE_MANAGER:
        """try:
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
            exit(3)"""
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
    app.config['MANAGER_STORAGE'] = '{0}/static/storage'.format(
        os.path.join(os.path.dirname(__file__)))

    """try:
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
        exit(3)"""


api = Api(app)

from modules.tasks import TaskFileApi
from modules.tasks import TaskManagementApi
from modules.tasks import TaskApi
from modules.tasks import TaskThumbnailListApi
from modules.tasks import TaskCompiledApi
from modules.tasks import TaskZipApi
from modules.tasks import TaskSupZipApi
from modules.tasks import TaskDepZipApi
api.add_resource(TaskFileApi, '/tasks/file/<int:job_id>')
api.add_resource(TaskManagementApi, '/tasks')
api.add_resource(TaskApi, '/tasks/<int:task_id>')
api.add_resource(TaskThumbnailListApi, '/tasks/thumbnails')
api.add_resource(TaskCompiledApi, '/tasks/compiled/<int:task_id>')
api.add_resource(TaskZipApi, '/tasks/zip/<int:job_id>')
api.add_resource(TaskSupZipApi, '/tasks/zip/sup/<int:job_id>')
api.add_resource(TaskDepZipApi, '/tasks/zip/dep/<int:job_id>')

from modules.workers import WorkerListApi
from modules.workers import WorkerApi
from modules.workers import WorkerStatusApi
api.add_resource(WorkerListApi, '/workers')
api.add_resource(WorkerApi, '/workers/<int:worker_id>')
api.add_resource(WorkerStatusApi, '/workers/status/<int:worker_id>')

from modules.settings import SettingsListApi
from modules.settings import SettingApi
api.add_resource(SettingsListApi, '/settings')
api.add_resource(SettingApi, '/settings/<string:name>')

def register_manager(port, name, has_virtual_workers):
    """This is going to be an HTTP request to the server with all the info for
    registering the render node. This is called by the runserver script.
    """
    import httplib
    import socket
    import time
    while True:
        try:
            connection = httplib.HTTPConnection(app.config['BRENDER_SERVER'])
            connection.request("GET", "/managers")
            break
        except socket.error:
            print ("Cant connect with Server, retrying...")
        time.sleep(1)

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

@app.errorhandler(404)
def not_found(error):
    response = jsonify({'code' : 404, 'message' : 'No interface defined for URL'})
    response.status_code = 404
    return response
