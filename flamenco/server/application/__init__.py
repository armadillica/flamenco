import os
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

# Initial configuration
from application import config_base
app.config.from_object(config_base.Config)

# If we are in a Docker container, override with some new defaults
if os.environ.get('IS_DOCKER'):
    from application import config_docker
    app.config.from_object(config_docker.Config)

# If a custom config file is specified, further override the config
if os.environ.get('FLAMENCO_SERVER_CONFIG'):
    app.config.from_envvar('FLAMENCO_SERVER_CONFIG')

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
api.add_resource(ManagerApi, '/managers/<int:manager_id>')

from modules.settings import SettingsListApi
from modules.settings import ManagersSettingsApi
api.add_resource(SettingsListApi, '/settings')
api.add_resource(ManagersSettingsApi, '/settings/managers')

from modules.settings import ManagerSettingApi
api.add_resource(ManagerSettingApi, '/settings/managers/<int:manager_id>/<setting_name>')

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
from modules.tasks import TaskStatusApi
from modules.tasks import TaskListApi
from modules.tasks import TaskGeneratorApi
from modules.tasks import TaskFileOutputApi
# Endpoint for generic task editing and log retrieval
api.add_resource(TaskApi, '/tasks/<int:task_id>')
# Temporary endpoint to edit the staus of a job (mainly via dashboard)
api.add_resource(TaskStatusApi, '/tasks/<int:task_id>/status')
# Listing of all tasks (usually filtered by job_id)
api.add_resource(TaskListApi, '/tasks')
# Endpoint queried by the managers to obtain new tasks
api.add_resource(TaskGeneratorApi, '/tasks/generate')
# Serves static path to download task files
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


