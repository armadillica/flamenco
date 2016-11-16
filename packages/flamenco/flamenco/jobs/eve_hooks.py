# -*- encoding: utf-8 -*-

import logging

from flask import abort
from eve.methods.post import post_internal

from flamenco.job_compilers import compilers


log = logging.getLogger(__name__)


def after_inserting_jobs(items):
    for item in items:
        # Prepare storage dir for the job files?
        # Generate tasks
        log.debug('Generating tasks for job {}'.format(item['_id']))
        create_tasks(item)


def create_tasks(job):
    """Send the job to the Job Compiler"""
    # from application.job_compilers.simple_blender_render import job_compiler
    module_name = 'flamenco.job_compilers.{}'.format(
        job['job_type'])
    try:
        compile_func = compilers['compile_{}'.format(job['job_type'])]
    except ImportError as e:
        print('Cant find module {0}: {1}'.format(module_name, e))
        return

    compile_func(job, create_task)


def create_task(job, commands, name, parents=None):
    task = {
        'job': job['_id'],
        'name': name,
        'job_type': job['job_type'],
        'commands': commands,
        'status': 'queued',
        'priority': job['priority'],
        'manager': job['manager'],
    }
    # Insertion of None parents is not supported
    if parents:
        task['parents'] = parents

    r = post_internal('tasks', task)
    if r[3] != 201:
        return abort(r[3])


def setup_app(app):
    app.on_inserted_jobs = after_inserting_jobs
    pass
