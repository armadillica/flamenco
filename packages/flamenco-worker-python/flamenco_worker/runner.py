"""Task runner."""

import abc
import asyncio
import logging

import attr

from . import attrs_extra
from . import documents
from . import worker

command_handlers = {}


@attr.s
class AbstractCommand(metaclass=abc.ABCMeta):
    worker = attr.ib(validator=attr.validators.instance_of(worker.FlamencoWorker))
    task_id = attr.ib(validator=attr.validators.instance_of(str))
    command_idx = attr.ib(validator=attr.validators.instance_of(int))

    # Set by @command_executor
    command_name = ''

    # Set by __call__()
    identifier = attr.ib(default=None, init=False,
                         validator=attr.validators.optional(attr.validators.instance_of(str)))
    _log = None

    async def run(self, settings: dict) -> bool:
        """Runs the command, parsing output and sending it back to the worker.

        Returns True when the command was succesful, and False otherwise.
        """

        self.identifier = '%s(task_id=%s, command_idx=%s)' % (
            self.command_name,
            self.task_id,
            self.command_idx)
        self._log = logging.getLogger('%s.%s' % (__name__, self.identifier))

        verr = self.validate(settings)
        if verr is not None:
            self.register_log('%s: Error in settings: %s' % (self.identifier, verr))
            self.worker.register_task_update(
                task_status='failed',
                activity='%s: Invalid settings: %s' % (self.identifier, verr),
            )
            return False

        self.worker.register_log('%s: Starting' % self.command_name)
        self.worker.register_task_update(
            activity='starting %s' % self.command_name,
            current_command_idx=self.command_idx,
            command_progress_percentage=0
        )

        try:
            await self.execute(settings)
        except Exception as ex:
            self._log.exception('Error executing.')
            self.worker.register_log('%s: Error executing: %s' % (self.identifier, ex))
            self.worker.register_task_update(
                task_status='failed',
                activity='%s: Error executing: %s' % (self.identifier, ex),
            )
            return False

        self.worker.register_log('%s: Finished' % self.command_name)
        self.worker.register_task_update(
            activity='finished %s' % self.command_name,
            current_command_idx=self.command_idx,
            command_progress_percentage=100
        )

        return True

    @abc.abstractmethod
    async def execute(self, settings: dict):
        """Executes the command."""

    def validate(self, settings: dict) -> str:
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
        self.worker.register_log(settings['message'])


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
        self.worker.register_log('Sleeping for %s seconds' % time_in_seconds)
        await asyncio.sleep(time_in_seconds)
        self.worker.register_log('Done sleeping for %s seconds' % time_in_seconds)
