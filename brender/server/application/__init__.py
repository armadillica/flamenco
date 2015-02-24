import os
import tempfile
from flask import Flask
from flask import jsonify
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.restful import Api
from flask.ext.migrate import Migrate

import logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

#RENDER_PATH = "render"

try:
    from application import config
    app.config['SQLALCHEMY_DATABASE_URI'] = config.Config.SQLALCHEMY_DATABASE_URI
    app.config['TMP_FOLDER']= config.Config.TMP_FOLDER
    app.config['THUMBNAIL_EXTENSIONS']= config.Config.THUMBNAIL_EXTENSIONS
    app.config['SERVER_STORAGE'] = config.Config.SERVER_STORAGE
except ImportError:
    from modules.managers.model import Manager
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(os.path.dirname(__file__), '../brender.sqlite'),
        TMP_FOLDER=tempfile.gettempdir(),
        THUMBNAIL_EXTENSIONS=set(['png']),
        SERVER_STORAGE = tempfile.gettempdir()
    )

api = Api(app)

from modules.projects import ProjectListApi
from modules.projects import ProjectApi
api.add_resource(ProjectListApi, '/projects')
api.add_resource(ProjectApi, '/projects/<int:project_id>')

from modules.workers import WorkerListApi
from modules.workers import WorkerApi
api.add_resource(WorkerListApi, '/workers')
api.add_resource(WorkerApi, '/workers/<int:worker_id>')

from modules.managers import ManagerListApi
from modules.managers import ManagerApi
api.add_resource(ManagerListApi, '/managers')
api.add_resource(ManagerApi, '/managers/<manager_uuid>')

from modules.settings import SettingsListApi
from modules.settings import RenderSettingsApi
api.add_resource(SettingsListApi, '/settings')
api.add_resource(RenderSettingsApi, '/settings/render')

from modules.filebrowser import FileBrowserApi
from modules.filebrowser import FileBrowserRootApi
api.add_resource(FileBrowserRootApi, '/browse')
api.add_resource(FileBrowserApi, '/browse/<path:path>')

from modules.jobs import JobListApi
from modules.jobs import JobApi
from modules.jobs import JobDeleteApi
from modules.jobs import JobThumbnailListApi
from modules.jobs import JobThumbnailApi
from modules.jobs import JobFileApi
from modules.jobs import JobFileOutputApi
api.add_resource(JobListApi, '/jobs')
api.add_resource(JobApi, '/jobs/<int:job_id>')
api.add_resource(JobDeleteApi, '/jobs/delete')
api.add_resource(JobThumbnailListApi, '/jobs/thumbnails')
api.add_resource(JobThumbnailApi, '/jobs/thumbnails/<job_id>')
api.add_resource(JobFileApi, '/jobs/file/<int:job_id>')
api.add_resource(JobFileOutputApi, '/jobs/file/output/<int:job_id>')

from modules.tasks import TaskApi
from modules.tasks import TaskFileOutputApi
api.add_resource(TaskApi, '/tasks')
api.add_resource(TaskFileOutputApi, '/task/file/output/<int:task_id>')

from modules.main import main
from modules.stats import stats

app.register_blueprint(main)
app.register_blueprint(stats, url_prefix='/stats')

@app.errorhandler(404)
def not_found(error):
    response = jsonify({'code': 404, 'message': 'No interface defined for URL'})
    response.status_code = 404
    return response


