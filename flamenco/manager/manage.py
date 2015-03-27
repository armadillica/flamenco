#! /usr/bin/env python
import os
import logging
import socket
import requests
from threading import Thread

from flask.ext.script import Manager
from flask.ext.migrate import MigrateCommand
from flask.ext.migrate import upgrade

from sqlalchemy import create_engine
from alembic.migration import MigrationContext

from application import app
from application import register_manager

manager = Manager(app)
manager.add_command('db', MigrateCommand)


@manager.command
def runserver():
    """This command is meant for development. If no configuration is found,
    we start the app listening from all hosts, from port 7777."""
    # Testig Alembic
    engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
    conn = engine.connect()
    context = MigrationContext.configure(conn)
    current_ver = context.get_current_revision()
    if not current_ver:
        print("Automatic DB Upgrade")
        print("Press Ctrl+C when finished")
        upgrade()
        print("Upgrade completed. Press Ctrl+C and runserver again.")

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


    # Register the manager to the server
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        if VIRTUAL_WORKERS:
            has_virtual_worker = 1
        else:
            has_virtual_worker = 0
        register_manager(PORT, HOSTNAME, has_virtual_worker)

    app.run(
        port=PORT,
        debug=DEBUG,
        host=HOST,
        threaded=True)


if __name__ == "__main__":
    manager.run()
