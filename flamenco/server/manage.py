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
        tasks_canceled = Task.query\
            .filter_by(job_id=job.id, status='canceled').count()
        tasks_count = job.tasks.count()

        tasks_status = {'count': tasks_count,
                        'finished': tasks_finished,
                        'failed': tasks_failed,
                        'canceled': tasks_canceled}

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


@manager.command
def evacuate_task_logs():
    import os
    import tarfile

    tasks_count = Task.query.count()
    index = 1

    while index < tasks_count:
        print "{0}/{1}".format(index, tasks_count)
        index += 1
        task = Task.query.get(index)
        if task and task.log:
            path_logs = os.path.join(
                app.config['SERVER_STORAGE'],
                str(task.job.project.id),
                str(task.job.id),
                'logs'
                )
            try:
                os.makedirs(path_logs)
            except Exception, e:
                print e
                pass
            print path_logs
            logfile_name = "{0}.txt".format(task.id)
            tarfile_name = "{0}.tar.gz".format(task.id)
            path_logfile = os.path.join(path_logs, logfile_name)
            path_tarfile = os.path.join(path_logs, tarfile_name)
            if not os.path.isfile(path_logfile) and not os.path.isfile(tarfile_name):
                with open(path_logfile, "w") as text_file:
                    text_file.write(task.log)
                with tarfile.open(path_tarfile, "w:gz") as tar:
                    tar.add(path_logfile, arcname=os.path.basename(path_tarfile))
                os.remove(path_logfile)

                print "Written log for task {0}".format(task.id)
                task.log = None
                db.session.commit()

if __name__ == "__main__":
    manager.run()
