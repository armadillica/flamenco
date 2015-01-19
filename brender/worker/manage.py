#! /usr/bin/python

from flask.ext.script import Manager
from application import app

manager = Manager(app)

@manager.command
def runserver():
    try:
        from application import config
        PORT = config.Config.PORT
        HOST = config.Config.HOST
        DEBUG = config.Config.DEBUG

    except ImportError:
        DEBUG = False
        PORT = 7777
        HOST = '0.0.0.0'

    app.run(port=PORT, debug=DEBUG, host=HOST)

if __name__ == "__main__":
    manager.run()
