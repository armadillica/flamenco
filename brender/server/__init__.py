import os
from flask import (Flask, jsonify)
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)
db = SQLAlchemy(app)

import model
# This is the default server configuration, in case the user will not provide one.
# The Application is configured to run on localhost and port 9999
# The brender.sqlite database will be created inside of the server folder
app.config.update(
    DEBUG=False,
    HOST='localhost',
    PORT=9999,
    SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(os.path.dirname(model.__file__), 'brender.sqlite')
)

from controllers.home import home
from controllers.jobs import jobs
from controllers.workers import workers
from controllers.shots import shots
from controllers.shows import shows
from controllers.settings import settings
from controllers.stats import stats

app.register_blueprint(home)
app.register_blueprint(workers, url_prefix='/workers')
app.register_blueprint(jobs, url_prefix='/jobs')
app.register_blueprint(shots, url_prefix='/shots')
app.register_blueprint(shows, url_prefix='/shows')
app.register_blueprint(settings, url_prefix='/settings')
app.register_blueprint(stats, url_prefix='/stats')


@app.errorhandler(404)
def not_found(error):
    response = jsonify({'code': 404,'message': 'No interface defined for URL'})
    response.status_code = 404
    return response


def run(user_config=None):
    config = app.config

    if user_config:
        config.from_object(user_config)

    #model.DATABASE = config['DATABASE']
    db.create_all()

    # Set SEVER_NAME value according to application configuration
    # config.update(
    #     SERVER_NAME="%s:%d" % (config['HOST'], config['PORT'])
    # )

    # Run application
    app.run(
        app.config['HOST'],
        app.config['PORT'],
    )
