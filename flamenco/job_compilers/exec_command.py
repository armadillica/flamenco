import shlex

from .abstract_compiler import AbstractJobCompiler
from . import commands, register_compiler


@register_compiler('exec-command')
class ExecCommand(AbstractJobCompiler):
    """Executes a single shell command; for debugging only."""

    def _compile(self, job):
        self._log.info('Compiling job %s', job['_id'])

        # Escape and recombine to normalise some quoting.
        cmdline = job['settings']['cmd']
        cmdbits = shlex.split(cmdline)
        cmdline = ' '.join(shlex.quote(bit) for bit in cmdbits)

        task_cmds = [
            commands.Exec(cmd=cmdline),
        ]

        self._create_task(job, task_cmds, 'exec-command', 'debug')
        self._log.info('Created 1 task for job %s', job['_id'])
