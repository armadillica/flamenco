#! /usr/bin/python

from flask.ext.script import Manager

from application import app

manager = Manager(app)

@manager.command
def runserver():
    app.run(
        port=8888,
        debug=True)


if __name__ == "__main__":
    manager.run()
