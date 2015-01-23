#! /usr/bin/env python

from flask.ext.script import Manager
from flask.ext.migrate import MigrateCommand

from application import app
from application import db
from tests import unittest

manager = Manager(app)
manager.add_command('db', MigrateCommand)

@manager.command
def runserver():
    """This command is meant for development. If no configuration is found,
    we start the app listening from all hosts, from port 9999."""
    try:
        from application import config
        PORT = config.Config.PORT
        DEBUG = config.Config.DEBUG
        HOST = config.Config.HOST
    except ImportError:
        DEBUG = False
        PORT = 9999
        HOST = '0.0.0.0'
    app.run(
        port=PORT,
        debug=DEBUG,
        host=HOST)

if __name__ == "__main__":
    manager.run()
