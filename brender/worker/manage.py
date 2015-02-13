#! /usr/bin/env python

from flask.ext.script import Manager
from application import app

manager = Manager(app)

import os
from threading import Thread
from application import controllers

@manager.command
@manager.option('-p', '--port', help='The port')
def runserver(port_number=None):
    try:
        from application import config
        PORT = config.Config.PORT
        HOST = config.Config.HOST
        DEBUG = config.Config.DEBUG

    except ImportError:
        DEBUG = False
        PORT = 5000
        HOST = '0.0.0.0'

    # Override port value (no matter if set in the config) if specified
    # at runtime with the --port argument.
    if port_number:
        PORT = int(port_number)

    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        register_thread = Thread(target=controllers.register_worker, args=(PORT,))
        register_thread.setDaemon(False)
        register_thread.start()

    app.run(port=PORT, debug=DEBUG, host=HOST)

if __name__ == "__main__":
    manager.run()
