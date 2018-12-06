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
from . import abstract_compiler, blender_render, blender_render_progressive, blender_video_chunks, \
    exec_command, sleep


def compile_job(job):
    """Creates tasks from the given job."""

    compiler = construct_job_compiler(job)
    compiler.compile(job)


def validate_job(job):
    """Validates job settings.

    :raises flamenco.exceptions.JobSettingError if the settings are bad.
    """

    compiler = construct_job_compiler(job)
    compiler.validate_job_settings(job)


def construct_job_compiler(job) -> abstract_compiler.AbstractJobCompiler:
    from flamenco import current_flamenco

    compiler_class = find_job_compiler(job)
    compiler = compiler_class(task_manager=current_flamenco.task_manager,
                              job_manager=current_flamenco.job_manager)

    return compiler


def find_job_compiler(job):
    from .abstract_compiler import AbstractJobCompiler

    # Get the compiler class for the job type.
    job_type = job['job_type']
    try:
        compiler_class = compilers[job_type]
    except KeyError:
        log.error('No compiler for job type %r', job_type)
        raise KeyError('No compiler for job type %r' % job_type)

    assert issubclass(compiler_class, AbstractJobCompiler)
    return compiler_class
