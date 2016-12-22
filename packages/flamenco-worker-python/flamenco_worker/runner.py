"""Task runner."""

import abc
import asyncio
import logging

import attr

from . import attrs_extra
from . import worker

command_handlers = {}


def command_executor(cmdname):
    """Class decorator, registers a command executor."""

    def decorator(cls):
        assert cmdname not in command_handlers

        command_handlers[cmdname] = cls
        cls.command_name = cmdname
        return cls

    return decorator


@attr.s
class AbstractCommand(metaclass=abc.ABCMeta):
    worker = attr.ib(validator=attr.validators.instance_of(worker.FlamencoWorker))
    task_id = attr.ib(validator=attr.validators.instance_of(str))
    command_idx = attr.ib(validator=attr.validators.instance_of(int))

    # Set by @command_executor
    command_name = attr.ib(default=None, init=False, validator=attr.validators.instance_of(str))

    # Set by __call__()
    identifier = attr.ib(default=None, init=False, validator=attr.validators.instance_of(str))
    _log = None

    def __call__(self, settings: dict):
        """Runs the command, parsing output and sending it back to the worker."""

        self.identifier = '%s(task_id=%s, command_idx=%s)' % (
            self.__class__.__name__,
            self.task_id,
            self.command_idx)
        self._log = logging.getLogger('%s.%s' % (__name__, self.identifier))

        verr = self.validate(settings)
        if verr is not None:
            self._log.warning('Invalid settings: %s', verr)
            # worker.command_error(self.command_name, verr)
            return

        try:
            self.execute(settings)
        except:
            self._log.exception('Error executing.')

    @abc.abstractmethod
    def execute(self, settings: dict):
        """Executes the command."""

    def validate(self, settings: dict) -> str:
        """Validates the settings for this command.

        If there is an error, a description of the error is returned.
        If the settings are valid, None is returned.

        By default all settings are considered valid.
        """

        return None

    def update_activity(self, new_activity):
        """Sends a new activity to the manager."""

        raise NotImplementedError()

    def upload_log(self, log):
        """Sends a new chunk of logs to the manager."""

        raise NotImplementedError()

    def handle_output_line(self, line: str):
        """Handles a line of output, parsing it into activity & log."""

        raise NotImplementedError()


@command_executor('echo')
class EchoCommand(AbstractCommand):
    def execute(self, settings: dict):
        raise NotImplementedError()


@attr.s
class TaskRunner:
    """Runs tasks, sending updates back to the worker."""

    shutdown_future = attr.ib(validator=attr.validators.instance_of(asyncio.Future))
    _log = attrs_extra.log('%s.TaskRunner' % __name__)

    async def execute(self, task: dict, fworker: worker.FlamencoWorker):
        raise NotImplementedError('Task execution not implemented yet.')
