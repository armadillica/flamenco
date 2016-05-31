import logging
from flask import abort
from eve.methods.post import post_internal

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
    module_name = 'application.modules.flamenco.job_compilers.{}'.format(
        job['job_type'])
    job_compiler = None
    try:
        module_loader = __import__(module_name, globals(), locals(),
                                   ['job_compiler'], 0)
        job_compiler = module_loader.job_compiler
    except ImportError as e:
        print('Cant find module {0}: {1}'.format(module_name, e))
        return

    job_compiler.compile(job, create_task)


def create_task(job, task_settings, name, child_id, parser):
    task = {
        'job': job['_id'],
        'name': name,
        'job_type': job['job_type'],
        'settings': task_settings,
        'status': 'queued',
        'priority': job['priority'],
        'manager': job['manager'],
        'parser': parser,
    }
    # Insertion of None child_id is not supported
    if child_id:
        task['child'] = child_id

    r = post_internal('tasks', task)
    if r[3] != 201:
        return abort(r[3])


def setup_app(app):
    # Permission hooks
    app.on_inserted_jobs += after_inserting_jobs

