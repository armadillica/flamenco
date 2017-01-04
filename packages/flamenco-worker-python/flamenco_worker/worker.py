import asyncio
import datetime

import attr

from . import attrs_extra
from . import documents
from . import upstream
from . import upstream_update_queue

# All durations/delays/etc are in seconds.
FETCH_TASK_FAILED_RETRY_DELAY = 10  # when we failed obtaining a task
FETCH_TASK_EMPTY_RETRY_DELAY = 5  # when there are no tasks to perform
FETCH_TASK_DONE_SCHEDULE_NEW_DELAY = 3  # after a task is completed

PUSH_LOG_MAX_ENTRIES = 10
PUSH_LOG_MAX_INTERVAL = datetime.timedelta(seconds=5)
PUSH_ACT_MAX_INTERVAL = datetime.timedelta(seconds=1)


class UnableToRegisterError(Exception):
    """Raised when the worker can't register at the manager.

    Will cause an immediate shutdown.
    """


@attr.s
class FlamencoWorker:
    manager = attr.ib(validator=attr.validators.instance_of(upstream.FlamencoManager))
    trunner = attr.ib()  # Instance of flamenco_worker.runner.TaskRunner
    tuqueue = attr.ib(validator=attr.validators.instance_of(upstream_update_queue.TaskUpdateQueue))
    job_types = attr.ib(validator=attr.validators.instance_of(list))
    worker_id = attr.ib(validator=attr.validators.instance_of(str))
    worker_secret = attr.ib(validator=attr.validators.instance_of(str))

    loop = attr.ib(validator=attr.validators.instance_of(asyncio.AbstractEventLoop))
    shutdown_future = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(asyncio.Future)))

    fetch_task_task = attr.ib(
        default=None, init=False,
        validator=attr.validators.optional(attr.validators.instance_of(asyncio.Task)))

    task_id = attr.ib(
        default=None, init=False,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    current_task_status = attr.ib(
        default=None, init=False,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    _queued_log_entries = attr.ib(default=attr.Factory(list), init=False)
    _queue_lock = attr.ib(default=attr.Factory(asyncio.Lock), init=False)
    last_log_push = attr.ib(
        default=datetime.datetime.now(),
        validator=attr.validators.optional(attr.validators.instance_of(datetime.datetime)))
    last_activity_push = attr.ib(
        default=datetime.datetime.now(),
        validator=attr.validators.optional(attr.validators.instance_of(datetime.datetime)))

    # Kept in sync with the task updates we send to upstream Manager, so that we can send
    # a complete Activity each time.
    last_task_activity = attr.ib(default=attr.Factory(documents.Activity))

    # Configuration
    push_log_max_interval = attr.ib(default=PUSH_LOG_MAX_INTERVAL,
                                    validator=attr.validators.instance_of(datetime.timedelta))
    push_log_max_entries = attr.ib(default=PUSH_LOG_MAX_ENTRIES,
                                   validator=attr.validators.instance_of(int))
    push_act_max_interval = attr.ib(default=PUSH_ACT_MAX_INTERVAL,
                                    validator=attr.validators.instance_of(datetime.timedelta))

    # Futures that represent delayed calls to push_to_master().
    # They are scheduled when logs & activities are registered but not yet pushed. They are
    # cancelled when a push_to_master() actually happens for another reason. There are different
    # futures for activity and log pushing, as these can have different max intervals.
    _push_log_to_manager = attr.ib(
        default=None, init=False,
        validator=attr.validators.optional(attr.validators.instance_of(asyncio.Future)))
    _push_act_to_manager = attr.ib(
        default=None, init=False,
        validator=attr.validators.optional(attr.validators.instance_of(asyncio.Future)))

    _log = attrs_extra.log('%s.FlamencoWorker' % __name__)

    async def startup(self):
        self._log.info('Starting up')

        if not self.worker_id or not self.worker_secret:
            await self.register_at_manager()

        # Once we know our ID and secret, update the manager object so that we
        # don't have to pass our authentication info each and every call.
        self.manager.auth = (self.worker_id, self.worker_secret)
        self.schedule_fetch_task()

    async def register_at_manager(self):
        import requests

        self._log.info('Registering at manager')

        self.worker_secret = generate_secret()
        platform = detect_platform()

        try:
            resp = await self.manager.post(
                '/register-worker',
                json={
                    'secret': self.worker_secret,
                    'platform': platform,
                    'supported_job_types': self.job_types,
                },
                auth=None,  # explicitly do not use authentication
                loop=self.loop,
            )
        except requests.ConnectionError:
            self._log.error('Unable to register at manager, aborting.')
            # TODO Sybren: implement a retry loop instead of aborting immediately.
            raise UnableToRegisterError()

        resp.raise_for_status()

        result = resp.json()
        self._log.info('Response: %s', result)
        self.worker_id = result['_id']

        self.write_registration_info()

    def write_registration_info(self):
        """Writes the current worker ID and secret to the home dir."""

        from . import config

        config.merge_with_home_config({
            'worker_id': self.worker_id,
            'worker_secret': self.worker_secret,
        })

    def mainloop(self):
        self._log.info('Entering main loop')

        # TODO: add "watchdog" task that checks the asyncio loop and ensures there is
        # always either a task being executed or a task fetch scheduled.
        self.loop.run_forever()

    def schedule_fetch_task(self, delay=0):
        """Schedules a task fetch.

        If a task fetch was already queued, that one is cancelled.

        :param delay: delay in seconds, after which the task fetch will be performed.
        """

        # The current task may still be running, as fetch_task() calls schedule_fetch_task() to
        # schedule a future run. This may result in the task not being awaited when we are
        # shutting down.
        if self.shutdown_future.done():
            self._log.warning('Shutting down, not scheduling another fetch-task task.')
            return

        self.fetch_task_task = asyncio.ensure_future(self.fetch_task(delay), loop=self.loop)

    def shutdown(self):
        """Gracefully shuts down any asynchronous tasks."""

        if self.fetch_task_task is None or self.fetch_task_task.done():
            return

        self._log.info('shutdown(): Cancelling task fetching task %s', self.fetch_task_task)
        self.fetch_task_task.cancel()

        # This prevents a 'Task was destroyed but it is pending!' warning on the console.
        # Sybren: I've only seen this in unit tests, so maybe this code should be moved
        # there, instead.
        try:
            self.loop.run_until_complete(self.fetch_task_task)
        except asyncio.CancelledError:
            pass

    async def fetch_task(self, delay: float):
        """Fetches a single task to perform from Flamenco Manager.

        :param delay: waits this many seconds before fetching a task.
        """

        import traceback
        import requests

        self._log.debug('Going to fetch task in %s seconds', delay)
        await asyncio.sleep(delay)

        # TODO: use exponential backoff instead of retrying every fixed N seconds.
        self._log.info('Fetching task')
        try:
            resp = await self.manager.post('/task', loop=self.loop)
        except requests.exceptions.RequestException as ex:
            self._log.warning('Error fetching new task, will retry in %i seconds: %s',
                              FETCH_TASK_FAILED_RETRY_DELAY, ex)
            self.schedule_fetch_task(FETCH_TASK_FAILED_RETRY_DELAY)
            return

        if resp.status_code == 204:
            self._log.info('No tasks available, will retry in %i seconds.',
                           FETCH_TASK_EMPTY_RETRY_DELAY)
            self.schedule_fetch_task(FETCH_TASK_EMPTY_RETRY_DELAY)
            return

        if resp.status_code != 200:
            self._log.warning('Error %i fetching new task, will retry in %i seconds.',
                              resp.status_code, FETCH_TASK_FAILED_RETRY_DELAY)
            self.schedule_fetch_task(FETCH_TASK_FAILED_RETRY_DELAY)
            return

        task_info = resp.json()
        self.task_id = task_info['_id']
        self._log.info('Received task: %s', self.task_id)
        self._log.debug('Received task: %s', task_info)

        try:
            await self.register_task_update(task_status='active')
            ok = await self.trunner.execute(task_info, self)
            if ok:
                await self.register_task_update(task_status='completed')
            else:
                self._log.error('Task %s failed', self.task_id)
                await self.register_task_update(task_status='failed')

            # Always end with a push to master, to flush whatever we still have queued.
            await self.push_to_manager()
        except Exception as ex:
            self._log.exception('Uncaught exception executing task %s' % self.task_id)
            try:
                with (await self._queue_lock):
                    self._queued_log_entries.append(traceback.format_exc())
                await self.register_task_update(
                    task_status='failed',
                    activity='Uncaught exception: %s %s' % (type(ex).__name__, ex),
                )

                # Always end with a push to master, to flush whatever we still have queued.
                await self.push_to_manager()
            except Exception:
                self._log.exception('While notifying manager of failure, another error happened.')
        finally:
            # Always schedule a new task run; after a little delay to not hammer the world
            # when we're in some infinite failure loop.
            self.schedule_fetch_task(FETCH_TASK_DONE_SCHEDULE_NEW_DELAY)

    async def push_to_manager(self, *, delay: datetime.timedelta=None):
        """Updates a task's status and activity.

        Uses the TaskUpdateQueue to handle persistent queueing.
        """

        if delay is not None:
            delay_sec = delay.total_seconds()
            self._log.debug('Scheduled delayed push to master in %r seconds', delay_sec)
            await asyncio.sleep(delay_sec)

        self._log.info('Updating task %s with status %r and activity %r',
                       self.task_id, self.current_task_status, self.last_task_activity)

        payload = attr.asdict(self.last_task_activity)
        payload['task_status'] = self.current_task_status

        now = datetime.datetime.now()
        self.last_activity_push = now

        # Cancel any pending push task, as we're pushing activities now.
        if self._push_act_to_manager is not None:
            self._push_act_to_manager.cancel()

        with (await self._queue_lock):
            if self._queued_log_entries:
                payload['log'] = '\n'.join(self._queued_log_entries)
                self._queued_log_entries.clear()
                self.last_log_push = now

                # Cancel any pending push task, as we're pushing logs now.
                if self._push_log_to_manager is not None:
                    self._push_log_to_manager.cancel()

        self.tuqueue.queue('/tasks/%s/update' % self.task_id, payload, loop=self.loop)

    async def register_task_update(self, *,
                                   task_status: str = None,
                                   **kwargs):
        """Stores the task status and activity, and possibly sends to Flamenco Manager.

        If the last update to Manager was long enough ago, or the task status changed,
        the info is sent to Manager. This way we can update command progress percentage
        hundreds of times per second, without worrying about network overhead.
        """

        self._log.debug('Task update: task_status=%s, %s', task_status, kwargs)

        # Update the current activity
        for key, value in kwargs.items():
            setattr(self.last_task_activity, key, value)

        if task_status is None:
            task_status_changed = False
        else:
            task_status_changed = self.current_task_status != task_status
            self.current_task_status = task_status

        if task_status_changed:
            self._log.info('Task changed status to %s, pushing to manager', task_status)
            await self.push_to_manager()
        elif datetime.datetime.now() - self.last_activity_push > self.push_act_max_interval:
            self._log.info('More than %s since last activity update, pushing to manager',
                           self.push_act_max_interval)
            await self.push_to_manager()
        elif self._push_act_to_manager is None or self._push_act_to_manager.done():
            # Schedule a future push to manager.
            self._push_act_to_manager = asyncio.ensure_future(
                self.push_to_manager(delay=self.push_act_max_interval))

    async def register_log(self, log_entry, *fmt_args):
        """Registers a log entry, and possibly sends all queued log entries to upstream Manager.

        Supports variable arguments, just like the logger.{info,warn,error}(...) family
        of methods.
        """

        from . import tz

        if fmt_args:
            log_entry %= fmt_args

        now = datetime.datetime.now(tz.tzutc()).isoformat()
        with (await self._queue_lock):
            self._queued_log_entries.append('%s: %s' % (now, log_entry))
            queue_size = len(self._queued_log_entries)

        if queue_size > self.push_log_max_entries:
            self._log.info('Queued up more than %i log entries, pushing to manager',
                           self.push_log_max_entries)
            await self.push_to_manager()
        elif datetime.datetime.now() - self.last_log_push > self.push_log_max_interval:
            self._log.info('More than %s since last log update, pushing to manager',
                           self.push_log_max_interval)
            await self.push_to_manager()
        elif self._push_log_to_manager is None or self._push_log_to_manager.done():
            # Schedule a future push to manager.
            self._push_log_to_manager = asyncio.ensure_future(
                self.push_to_manager(delay=self.push_log_max_interval))


def generate_secret() -> str:
    """Generates a 64-character secret key."""

    import random
    import string

    randomizer = random.SystemRandom()
    tokens = string.ascii_letters + string.digits
    secret = ''.join(randomizer.choice(tokens) for _ in range(64))

    return secret


def detect_platform() -> str:
    """Detects the platform, returning 'linux', 'windows' or 'darwin'.

    Raises an exception when the current platform cannot be detected
    as one of those three.
    """

    import platform

    plat = platform.system().lower()
    if not plat:
        raise EnvironmentError('Unable to determine platform.')

    if plat in {'linux', 'windows', 'darwin'}:
        return plat

    raise EnvironmentError('Unable to determine platform; unknown platform %r', plat)
