#! /usr/bin/env python

# import logging
import json

from flask.ext.script import Manager
from flask.ext.migrate import MigrateCommand
# from flask.ext.migrate import current
from flask.ext.migrate import upgrade
from sqlalchemy import create_engine
from alembic.migration import MigrationContext

from application import app
from application import db
# from tests import unittest

from application.modules.jobs.model import Job
from application.modules.tasks.model import Task

manager = Manager(app)
manager.add_command('db', MigrateCommand)


@manager.command
def compute_tasks_status():
    jobs = Job.query.all()
    for job in jobs:
        tasks_finished = Task.query\
            .filter_by(job_id=job.id, status='finished').count()
        tasks_failed = Task.query\
            .filter_by(job_id=job.id, status='failed').count()
        tasks_aborted = Task.query\
            .filter_by(job_id=job.id, status='aborted').count()
        tasks_count = job.tasks.count()

        tasks_status = {'count': tasks_count,
                        'finished': tasks_finished,
                        'failed': tasks_failed,
                        'aborted': tasks_aborted}

        job.tasks_status = json.dumps(tasks_status)
        db.session.add(job)
        db.session.commit()


@manager.command
def runserver():
    """This command is meant for development. If no configuration is found,
    we start the app listening from all hosts, from port 9999."""

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
    except ImportError:
        DEBUG = False
        PORT = 9999
        HOST = '0.0.0.0'
    app.run(
        port=PORT,
        debug=DEBUG,
        host=HOST,
        threaded=True)

if __name__ == "__main__":
    manager.run()
