"""Task runner."""

import abc
import asyncio
import logging

import attr

from . import attrs_extra
from . import worker

# Timeout of subprocess.stdout.readline() call.
SUBPROC_READLINE_TIMEOUT = 3600  # seconds

command_handlers = {}


class CommandExecutionError(Exception):
    """Raised when there was an error executing a command."""
    pass


@attr.s
class AbstractCommand(metaclass=abc.ABCMeta):
    worker = attr.ib(validator=attr.validators.instance_of(worker.FlamencoWorker))
    task_id = attr.ib(validator=attr.validators.instance_of(str))
    command_idx = attr.ib(validator=attr.validators.instance_of(int))

    # Set by @command_executor
    command_name = ''

    # Set by __attr_post_init__()
    identifier = attr.ib(default=None, init=False,
                         validator=attr.validators.optional(attr.validators.instance_of(str)))
    _log = attr.ib(default=None, init=False,
                   validator=attr.validators.optional(attr.validators.instance_of(logging.Logger)))

    def __attrs_post_init__(self):
        self.identifier = '%s(task_id=%s, command_idx=%s)' % (
            self.command_name,
            self.task_id,
            self.command_idx)
        self._log = logging.getLogger('%s.%s' % (__name__, self.identifier))

    async def run(self, settings: dict) -> bool:
        """Runs the command, parsing output and sending it back to the worker.

        Returns True when the command was succesful, and False otherwise.
        """

        verr = self.validate(settings)
        if verr is not None:
            self._log.warning('%s: Error in settings: %s', self.identifier, verr)
            await self.worker.register_log('%s: Error in settings: %s', self.identifier, verr)
            await self.worker.register_task_update(
                task_status='failed',
                activity='%s: Invalid settings: %s' % (self.identifier, verr),
            )
            return False

        await self.worker.register_log('%s: Starting' % self.command_name)
        await self.worker.register_task_update(
            activity='starting %s' % self.command_name,
            current_command_idx=self.command_idx,
            command_progress_percentage=0
        )

        try:
            await self.execute(settings)
        except CommandExecutionError as ex:
            # This is something we threw ourselves, and there is no need to log the traceback.
            self._log.warning('Error executing: %s', ex)
            await self._register_exception(ex)
            return False
        except Exception as ex:
            # This is something unexpected, so do log the traceback.
            self._log.exception('Error executing.')
            await self._register_exception(ex)
            return False

        await self.worker.register_log('%s: Finished' % self.command_name)
        await self.worker.register_task_update(
            activity='finished %s' % self.command_name,
            current_command_idx=self.command_idx,
            command_progress_percentage=100
        )

        return True

    async def _register_exception(self, ex: Exception):
        """Registers an exception with the worker, and set the task status to 'failed'."""

        await self.worker.register_log('%s: Error executing: %s' % (self.identifier, ex))
        await self.worker.register_task_update(
            task_status='failed',
            activity='%s: Error executing: %s' % (self.identifier, ex),
        )

    @abc.abstractmethod
    async def execute(self, settings: dict):
        """Executes the command.

        An error should be indicated by an exception.
        """

    def validate(self, settings: dict):
        """Validates the settings for this command.

        If there is an error, a description of the error is returned.
        If the settings are valid, None is returned.

        By default all settings are considered valid.
        """

        return None


def command_executor(cmdname):
    """Class decorator, registers a command executor."""

    def decorator(cls):
        assert cmdname not in command_handlers

        command_handlers[cmdname] = cls
        cls.command_name = cmdname
        return cls

    return decorator


@attr.s
class TaskRunner:
    """Runs tasks, sending updates back to the worker."""

    shutdown_future = attr.ib(validator=attr.validators.instance_of(asyncio.Future))
    last_command_idx = attr.ib(default=0, init=False)

    _log = attrs_extra.log('%s.TaskRunner' % __name__)

    async def execute(self, task: dict, fworker: worker.FlamencoWorker) -> bool:
        """Executes a task, returns True iff the entire task was run succesfully."""

        task_id = task['_id']

        for cmd_idx, cmd_info in enumerate(task['commands']):
            self.last_command_idx = cmd_idx

            # Figure out the command name
            cmd_name = cmd_info.get('name')
            if not cmd_name:
                raise ValueError('Command %i of task %s has no name' % (cmd_idx, task_id))

            cmd_settings = cmd_info.get('settings')
            if cmd_settings is None or not isinstance(cmd_settings, dict):
                raise ValueError('Command %i of task %s has malformed settings %r' %
                                 (cmd_idx, task_id, cmd_settings))

            # Find the handler class
            try:
                cmd_cls = command_handlers[cmd_name]
            except KeyError:
                raise ValueError('Command %i of task %s has unknown command name %r' %
                                 (cmd_idx, task_id, cmd_name))

            # Construct & execute the handler.
            cmd = cmd_cls(
                worker=fworker,
                task_id=task_id,
                command_idx=cmd_idx,
            )
            success = await cmd.run(cmd_settings)

            if not success:
                self._log.warning('Command %i of task %s was not succesful, aborting task.',
                                  cmd_idx, task_id)
                return False

        self._log.info('Task %s completed succesfully.', task_id)
        return True


@command_executor('echo')
class EchoCommand(AbstractCommand):
    def validate(self, settings: dict):
        try:
            msg = settings['message']
        except KeyError:
            return 'Missing "message"'

        if not isinstance(msg, str):
            return 'Message must be a string'

    async def execute(self, settings: dict):
        await self.worker.register_log(settings['message'])


@command_executor('sleep')
class SleepCommand(AbstractCommand):
    def validate(self, settings: dict):
        try:
            sleeptime = settings['time_in_seconds']
        except KeyError:
            return 'Missing "time_in_seconds"'

        if not isinstance(sleeptime, (int, float)):
            return 'time_in_seconds must be an int or float'

    async def execute(self, settings: dict):
        time_in_seconds = settings['time_in_seconds']
        await self.worker.register_log('Sleeping for %s seconds' % time_in_seconds)
        await asyncio.sleep(time_in_seconds)
        await self.worker.register_log('Done sleeping for %s seconds' % time_in_seconds)


@attr.s
class AbstractSubprocessCommand(AbstractCommand):
    readline_timeout = attr.ib(default=SUBPROC_READLINE_TIMEOUT)

    async def subprocess(self, args: list):
        import subprocess
        import shlex

        cmd_to_log = ' '.join(shlex.quote(s) for s in args)
        await self.worker.register_log('Executing %s', cmd_to_log)

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            limit=800,  # limit on the StreamReader buffer.
        )

        while not proc.stdout.at_eof():
            try:
                line = await asyncio.wait_for(proc.stdout.readline(),
                                              self.readline_timeout)
            except asyncio.TimeoutError:
                raise CommandExecutionError('Command timed out after %i seconds' %
                                            self.readline_timeout)

            if len(line) == 0:
                # EOF received, so let's bail.
                break

            try:
                line = line.decode('utf8')
            except UnicodeDecodeError as ex:
                try:
                    proc.kill()
                except ProcessLookupError:
                    # The process is already stopped, so killing is impossible. That's ok.
                    pass
                await proc.wait()
                raise CommandExecutionError('Command produced non-UTF8 output, aborting: %s' % ex)

            line = line.rstrip()
            line = await self.process_line(line)
            if line is not None:
                self._log.info('Read line: %s', line)
                await self.worker.register_log(line)

        retcode = await proc.wait()
        self._log.info('Command %r stopped with status code %s', args, retcode)

        if retcode:
            raise CommandExecutionError('Command failed with status %s' % retcode)

    async def process_line(self, line: str) -> str:
        """Processes the line, returning None to ignore it."""

        return '> %s' % line


@command_executor('exec')
class ExecCommand(AbstractSubprocessCommand):
    def validate(self, settings: dict):
        try:
            cmd = settings['cmd']
        except KeyError:
            return 'Missing "cmd"'

        if not isinstance(cmd, str):
            return '"cmd" must be a string'
        if not cmd:
            return '"cmd" may not be empty'

    async def execute(self, settings: dict):
        import shlex
        await self.subprocess(shlex.split(settings['cmd']))
