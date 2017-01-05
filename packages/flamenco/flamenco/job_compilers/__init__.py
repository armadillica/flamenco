import logging

log = logging.getLogger(__name__)

# Mapping from job type to compiler class.
compilers = {}


def register_compiler(job_type):
    """Registers the decorated class as job compiler."""

    def decorator(cls):
        compilers[job_type] = cls
        return cls

    return decorator


# Import subpackages to register the compilers
from . import sleep, blender_render


def compile_job(job):
    """Creates tasks from the given job."""

    from flamenco import current_flamenco
    from .abstract_compiler import AbstractJobCompiler

    # Get the compiler class for the job type.
    job_type = job['job_type']
    try:
        compiler_class = compilers[job_type]
    except KeyError:
        log.error('No compiler for job type %r', job_type)
        raise KeyError('No compiler for job type %r' % job_type)

    assert issubclass(compiler_class, AbstractJobCompiler)

    compiler = compiler_class(task_manager=current_flamenco.task_manager)
    compiler.compile(job)
