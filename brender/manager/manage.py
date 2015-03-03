#! /usr/bin/env python
import os
import logging
import socket
import requests
from threading import Thread
from threading import Timer
from requests.exceptions import ConnectionError
from requests.exceptions import Timeout

from flask.ext.script import Manager
from flask.ext.migrate import MigrateCommand

from application import app
from application import register_manager

manager = Manager(app)
manager.add_command('db', MigrateCommand)

loop_thread = None

def manager_loop(HOST):
    global loop_thread
    try:
        requests.get(HOST, timeout=5)
    except ConnectionError, e:
        print(e)
    except Timeout, e:
        print (e)
    loop_thread = Timer(10, manager_loop, args = {HOST})
    loop_thread.start()


@manager.command
def runserver():
    """This command is meant for development. If no configuration is found,
    we start the app listening from all hosts, from port 7777."""
    #Testing Database
    from application.modules.settings.model import Setting
    from sqlalchemy.exc import OperationalError
    try:
        Setting.query.first()
    except OperationalError:
        logging.error("Please run \"python manager.py db upgrade\" to initialize the database")
        exit(3)

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
            has_virtual_worker = 1
        else:
            has_virtual_worker = 0
        register_thread = Thread(
            target=register_manager,
            args=(PORT, HOSTNAME, has_virtual_worker))
        register_thread.setDaemon(False)
        register_thread.start()

        #manager_loop ("http://{0}:{1}/workers/loop".format(HOST,PORT))

    app.run(
        port=PORT,
        debug=DEBUG,
        host=HOST,
        threaded=True)

    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        global loop_thread
        if loop_thread:
            loop_thread.cancel()

if __name__ == "__main__":
    manager.run()
