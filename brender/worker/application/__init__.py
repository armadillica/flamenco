import os
from threading import Thread
from flask import Flask

app = Flask(__name__)

try:
    import config
    app.config.update(
        BRENDER_MANAGER = config.Config.BRENDER_MANAGER
    )
except ImportError:
    app.config['BRENDER_MANAGER'] = 'localhost:7777'

from controllers import controller_bp
app.register_blueprint(controller_bp, url_prefix='/')

# Use multiprocessing to register the client the worker to the server
# while the worker app starts up
#def run(user_config=None):
#    config = controllers.app.config
#
#    if user_config:
#        config.from_object(user_config)
#
#    controllers.BRENDER_SERVER = config['BRENDER_MANAGER']
#
#    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
#        register_thread = Thread(target=controllers.register_worker)
#        register_thread.setDaemon(False)
#        register_thread.start()
#
#    controllers.app.run(config['HOST'], config['PORT'])
