# Mapping from job type to compiler class.
compilers = {}


def register_compiler(job_type):
    """Registers the decorated class as job compiler."""

    def decorator(cls):
        compilers[job_type] = cls
        return cls

    return decorator


# Import subpackages to register the compilers
from . import sleep


def compile_job(job):
    """Creates tasks from the given job."""

    from flamenco import current_flamenco
    from .job_types import AbstractJobCompiler

    # Get the compiler class for the job type.
    job_type = job['job_type']
    compiler_class = compilers[job_type]
    assert issubclass(compiler_class, AbstractJobCompiler)

    compiler = compiler_class(task_manager=current_flamenco.task_manager)
    compiler.compile(job)
