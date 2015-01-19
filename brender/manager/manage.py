#! /usr/bin/python
import os
import socket
from threading import Thread

from flask.ext.script import Manager
from flask.ext.migrate import MigrateCommand

from application import app
from application import db
from application import register_manager
from tests import unittest

manager = Manager(app)
manager.add_command('db', MigrateCommand)

@manager.command
def runserver():
    """This command is meant for development. If no configuration is found,
    we start the app listening from all hosts, from port 7777."""

    try:
        from application import config
        PORT = config.Config.PORT
        DEBUG = config.Config.DEBUG
        HOST = config.Config.HOST
        HOSTNAME = config.Config.HOSTNAME
        VIRTUAL_WORKERS = config.Config.VIRTUAL_WORKERS
    except ImportError:
        DEBUG = False
        PORT = 7777 
        HOST = '0.0.0.0'
        VIRTUAL_WORKERS = False
        HOSTNAME = socket.gethostname()


    # Use multiprocessing to register the manager to the server
    # while the manager app starts up
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        if VIRTUAL_WORKERS:
            total_workers = None
        else:
            total_workers = 0
        register_thread = Thread(
            target=register_manager,
            args=(PORT, HOSTNAME, total_workers))
        register_thread.setDaemon(False)
        register_thread.start()

    app.run(
        port=PORT,
        debug=DEBUG,
        host=HOST)

if __name__ == "__main__":
    manager.run()
