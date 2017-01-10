"""Task runner."""

import abc
import asyncio
import asyncio.subprocess
import logging
import re
import typing

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
    worker = attr.ib(validator=attr.validators.instance_of(worker.FlamencoWorker),
                     repr=False)
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
        except asyncio.CancelledError as ex:
            self._log.warning('Command execution was canceled')
            raise
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

    async def abort(self):
        """Aborts the command. This may or may not be actually possible.

        A subprocess that's started by this command will be killed.
        However, any asyncio coroutines that are not managed by this command
        (such as the 'run' function) should be cancelled by the caller.
        """

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

    def __attrs_post_init__(self):
        self.current_command = None

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
            self.current_command = cmd
            success = await cmd.run(cmd_settings)

            if not success:
                self._log.warning('Command %i of task %s was not succesful, aborting task.',
                                  cmd_idx, task_id)
                return False

        self._log.info('Task %s completed succesfully.', task_id)
        return True

    async def abort_current_task(self):
        """Aborts the current task by aborting the currently running command.

        Asynchronous, because a subprocess has to be wait()ed upon before returning.
        """

        if self.current_command is None:
            self._log.info('abort_current_task: no command running, nothing to abort.')
            return

        self._log.warning('abort_current_task: Aborting command %s', self.current_command)
        await self.current_command.abort()


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
    proc = attr.ib(validator=attr.validators.instance_of(asyncio.subprocess.Process),
                   init=False)

    async def subprocess(self, args: list):
        import subprocess
        import shlex

        cmd_to_log = ' '.join(shlex.quote(s) for s in args)
        await self.worker.register_log('Executing %s', cmd_to_log)

        self.proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            limit=800,  # limit on the StreamReader buffer.
        )

        try:
            while not self.proc.stdout.at_eof():
                try:
                    line = await asyncio.wait_for(self.proc.stdout.readline(),
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
                    await self.abort()
                    raise CommandExecutionError('Command produced non-UTF8 output, '
                                                'aborting: %s' % ex)

                line = line.rstrip()
                self._log.info('Read line: %s', line)
                line = await self.process_line(line)
                if line is not None:
                    await self.worker.register_log(line)

            retcode = await self.proc.wait()
            self._log.info('Command %r stopped with status code %s', args, retcode)

            if retcode:
                raise CommandExecutionError('Command failed with status %s' % retcode)
        except asyncio.CancelledError:
            self._log.info('asyncio task got canceled, killing subprocess.')
            await self.abort()
            raise

    async def process_line(self, line: str) -> typing.Optional[str]:
        """Processes the line, returning None to ignore it."""

        return '> %s' % line

    async def abort(self):
        """Aborts the command by killing the subprocess."""

        if self.proc is None or self.proc == attr.NOTHING:
            self._log.debug("No process to kill. That's ok.")
            return

        self._log.info('Aborting subprocess')
        try:
            self.proc.kill()
        except ProcessLookupError:
            # The process is already stopped, so killing is impossible. That's ok.
            self._log.debug("The process was already stopped, aborting is impossible. That's ok.")
            return

        retval = await self.proc.wait()
        self._log.info('The process aborted with status code %s', retval)


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


@command_executor('blender_render')
class BlenderRenderCommand(AbstractSubprocessCommand):
    re_global_progress = attr.ib(init=False)
    re_time = attr.ib(init=False)
    re_remaining = attr.ib(init=False)
    re_status = attr.ib(init=False)
    re_path_not_found = attr.ib(init=False)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        # Delay regexp compilation until a BlenderRenderCommand is actually constructed.
        self.re_global_progress = re.compile(
            r"^Fra:(?P<fra>\d+) Mem:(?P<mem>[^ ]+) \(.*?, Peak (?P<peakmem>[^ ]+)\)")
        self.re_time = re.compile(
            r'\| Time:((?P<hours>\d+):)?(?P<minutes>\d+):(?P<seconds>\d+)\.(?P<hunds>\d+) ')
        self.re_remaining = re.compile(
            r'\| Remaining:((?P<hours>\d+):)?(?P<minutes>\d+):(?P<seconds>\d+)\.(?P<hunds>\d+) ')
        self.re_status = re.compile(r'\| (?P<status>[^\|]+)\s*$')
        self.re_path_not_found = re.compile(r"Warning: Path '.*' not found")

    def _setting(self, settings: dict, key: str, is_required: bool) -> (
            typing.Any, typing.Optional[str]):
        """Parses a setting, returns either (value, None) or (None, errormsg)"""

        try:
            value = settings[key]
        except KeyError:
            if is_required:
                return None, 'Missing "%s"' % key
            return None, None

        if not isinstance(value, str):
            return None, '"%s" must be a string' % key

        return value, None

    def validate(self, settings: dict):
        import os.path

        blender_cmd, err = self._setting(settings, 'blender_cmd', True)
        if err:
            return err
        if not os.path.exists(blender_cmd):
            return 'blender_cmd %r does not exist' % blender_cmd

        filepath, err = self._setting(settings, 'filepath', True)
        if err:
            return err
        if not os.path.exists(filepath):
            return 'filepath %r does not exist' % filepath

        render_output, err = self._setting(settings, 'render_output', False)
        if err:
            return err
        if render_output:
            dirname = os.path.dirname(render_output)
            if not os.path.exists(dirname):
                return '"render_output": dir %s does not exist' % dirname

        _, err = self._setting(settings, 'frames', False)
        if err:
            return err
        _, err = self._setting(settings, 'render_format', False)
        if err:
            return err

        return None

    async def execute(self, settings: dict):
        cmd = [
            settings['blender_cmd'],
            '--enable-autoexec',
            '-noaudio',
            '--background',
            settings['filepath'],
        ]
        if 'render_output' in settings:
            cmd.extend(['--render-output', settings['render_output']])
        if 'format' in settings:
            cmd.extend(['--render-format', settings['format']])
        if 'frames' in settings:
            cmd.extend(['--render-frame', settings['frames']])

        await self.worker.register_task_update(activity='Starting Blender')
        await self.subprocess(cmd)

    def parse_render_line(self, line: str) -> typing.Optional[dict]:
        """Parses a single line of render progress.

        Returns None if this line does not contain render progress.
        """

        m = self.re_global_progress.search(line)
        if not m:
            return None
        info = m.groupdict()
        info['fra'] = int(info['fra'])

        m = self.re_time.search(line)
        if m:
            info['time_sec'] = (3600 * int(m.group('hours') or 0) +
                                60 * int(m.group('minutes')) +
                                int(m.group('seconds')) +
                                int(m.group('hunds')) / 100)

        m = self.re_remaining.search(line)
        if m:
            info['remaining_sec'] = (3600 * int(m.group('hours') or 0) +
                                     60 * int(m.group('minutes')) +
                                     int(m.group('seconds')) +
                                     int(m.group('hunds')) / 100)

        m = self.re_status.search(line)
        if m:
            info['status'] = m.group('status')

        return info

    async def process_line(self, line: str) -> typing.Optional[str]:
        """Processes the line, returning None to ignore it."""

        # See if there are any warnings about missing files. If so, we simply abort the render.
        if 'Warning: Unable to open' in line or self.re_path_not_found.search(line):
            await self.worker.register_task_update(activity=line)
            raise CommandExecutionError(line)

        render_info = self.parse_render_line(line)
        if render_info:
            # Render progress. Not interesting to log all of them, but we do use
            # them to update the render progress.
            # TODO: For now we return this as a string, but at some point we may want
            # to consider this as a subdocument.
            if 'remaining_sec' in render_info:
                fmt = 'Fra:{fra} Mem:{mem} | Time:{time_sec} | Remaining:{remaining_sec} | {status}'
                activity = fmt.format(**render_info)
            else:
                self._log.debug('Unable to find remaining time in line: %s', line)
                activity = line
            await self.worker.register_task_update(activity=activity)
            return None

        # Not a render progress line; just log it for now.
        return '> %s' % line
