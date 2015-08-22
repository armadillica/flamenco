#! /usr/bin/env python
import os
import logging
import socket
import requests
import json
from threading import Thread

from flask.ext.script import Manager
from flask.ext.migrate import MigrateCommand
from flask.ext.migrate import upgrade

from sqlalchemy import create_engine
from alembic.migration import MigrationContext

from application import app
from application import db
from application import register_manager

from application.modules.job_types.model import JobType

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

    # TODO: search for the task_compilers and ask for required commands accordigly
    # Render Config
    render_config = JobType.query.filter_by(name='simple_blender_render').first()
    if not render_config:
        configuration = {'commands' : {
            'default' : {
                'Linux' : '',
                'Darwin' : '',
                'Windows' : ''
            }
        }}
        print("Please enter the shared blender path for the simple_blender_render command")
        configuration['commands']['default']['Linux'] = raw_input('Linux path: ')
        configuration['commands']['default']['Darwin'] = raw_input('OSX path: ')
        configuration['commands']['default']['Windows'] = raw_input('Windows path: ')

        render_config = JobType(
            name='simple_blender_render',
            properties=json.dumps(configuration))
        db.session.add(render_config)
        render_config = JobType(
            name='blender_simple_render',
            properties=json.dumps(configuration))
        db.session.add(render_config)
        db.session.commit()
    # Bake config
    bake_config = JobType.query.filter_by(name='blender_bake_anim_cache').first()
    if not bake_config:
        configuration = {'commands' : {
            'default' : {
                'Linux' : '',
                'Darwin' : '',
                'Windows' : ''
            }
        }}
        print("Please enter the shared blender path for the blender_bake_anim_cache command")
        configuration['commands']['default']['Linux'] = raw_input('Linux path: ')
        configuration['commands']['default']['Darwin'] = raw_input('OSX path: ')
        configuration['commands']['default']['Windows'] = raw_input('Windows path: ')

        bake_config = JobType(
            name='blender_bake_anim_cache',
            properties=json.dumps(configuration))
        db.session.add(bake_config)
        db.session.commit()

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
