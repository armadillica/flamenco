#! /usr/bin/env python2

from flask.ext.script import Manager
from application import app

manager = Manager(app)

@manager.command
def runserver():
    """This command is meant for development. If no configuration is found,
    we start the app listening from all hosts, from port 8888."""
    try:
        from application import config
        PORT = config.Config.PORT
        DEBUG = config.Config.DEBUG
        HOST = config.Config.HOST
    except ImportError:
        DEBUG = True
        PORT = 8888
        HOST = '0.0.0.0'
    app.run(
        port=PORT,
        debug=DEBUG,
        host=HOST)


if __name__ == "__main__":
    manager.run()
