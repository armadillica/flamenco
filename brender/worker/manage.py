#! /usr/bin/env python

from flask.ext.script import Manager
from application import app

manager = Manager(app)

import os
from threading import Thread
from threading import Timer
from application import controllers


@manager.command
@manager.option('-p', '--port', help='The port')
def runserver(port_number=None):
    global LOOP_THREAD
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
        #controllers.register_worker(PORT)
        LOOP_THREAD = controllers.worker_loop()

    app.run(port=PORT, debug=DEBUG, host=HOST)

    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        print (LOOP_THREAD)
        if LOOP_THREAD:
            LOOP_THREAD.cancel()

if __name__ == "__main__":
    manager.run()
