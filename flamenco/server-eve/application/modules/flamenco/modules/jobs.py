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
                                   ['JobCompiler'], 0)
        job_compiler = module_loader.JobCompiler
    except ImportError as e:
        print('Cant find module {0}: {1}'.format(module_name, e))
        return

    job_compiler.compile(job, create_task)


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
    # Permission hooks
    app.on_inserted_jobs += after_inserting_jobs

