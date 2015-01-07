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

#RENDER_PATH = "render"


# This is the default server configuration, in case the user will not provide one.
# The Application is configured to run on localhost and port 9999
# The brender.sqlite database will be created inside of the server folder
try:
    import config
    app.config.from_object(config.Server)
except:
    from modules.managers.model import Manager
    app.config.update(
        DEBUG=False,
        HOST='localhost',
        PORT=9999,
        SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(os.path.dirname(__file__), '../brender.sqlite'),
        MANAGERS = [ \
            Manager(id=1, name='debian', ip_address='127.0.0.1', port=7777, total_workers=1) \
        ]
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

from modules.managers import ManagersApi
api.add_resource(ManagersApi, '/managers')

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
api.add_resource(JobListApi, '/jobs')
api.add_resource(JobApi, '/jobs/<int:job_id>')
api.add_resource(JobDeleteApi, '/jobs/delete')

from modules.tasks import TaskApi
api.add_resource(TaskApi, '/tasks')

from modules.main import main
from modules.stats import stats

app.register_blueprint(main)
app.register_blueprint(stats, url_prefix='/stats')


@app.errorhandler(404)
def not_found(error):
    response = jsonify({'code': 404,'message': 'No interface defined for URL'})
    response.status_code = 404
    return response


