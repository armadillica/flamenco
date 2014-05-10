from flask import Flask

app = Flask(__name__)

app.config.update(
    SECRET_KEY='A0Zr98j/3yX R~XHH!jmN]LWX/,?RT',
    DEBUG=False,
    HOST='localhost',
    PORT=8888,
    BRENDER_SERVER='localhost:9999'
)

from dashboard.controllers.controllers import *
from dashboard.controllers.shots import shots
app.register_blueprint(shots, url_prefix='/shots')

def run(user_config=None):
    config = app.config

    if user_config:
        config.from_object(user_config)

    config.update(
        SERVER_NAME="%s:%s" % (config['HOST'], config['PORT'])
    )

    app.run(config['HOST'], config['PORT'])
