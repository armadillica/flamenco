import asyncio
import datetime

import attr

from . import attrs_extra
from . import documents
from . import upstream

# All durations/delays/etc are in seconds.
FETCH_TASK_FAILED_RETRY_DELAY = 10  # when we failed obtaining a task
FETCH_TASK_EMPTY_RETRY_DELAY = 5  # when there are no tasks to perform

PUSH_LOG_MAX_ENTRIES = 10
PUSH_LOG_MAX_INTERVAL = datetime.timedelta(seconds=5)
PUSH_ACT_MAX_INTERVAL = datetime.timedelta(seconds=10)


@attr.s
class FlamencoWorker:
    manager = attr.ib(validator=attr.validators.instance_of(upstream.FlamencoManager))
    trunner = attr.ib()  # Instance of flamenco_worker.runner.TaskRunner
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
    queued_log_entries = attr.ib(default=attr.Factory(list), init=False)
    last_log_push = attr.ib(
        default=datetime.datetime.now(),
        validator=attr.validators.optional(attr.validators.instance_of(datetime.datetime)))
    last_activity_push = attr.ib(
        default=datetime.datetime.now(),
        validator=attr.validators.optional(attr.validators.instance_of(datetime.datetime)))

    # Kept in sync with the task updates we send to upstream Master, so that we can send
    # a complete Activity each time.
    last_task_activity = attr.ib(default=attr.Factory(documents.Activity))

    _log = attrs_extra.log('%s.FlamencoWorker' % __name__)

    def startup(self):
        self._log.info('Starting up')

        if not self.worker_id or not self.worker_secret:
            self.register_at_manager()

        self.schedule_fetch_task()

    def register_at_manager(self):
        self._log.info('Registering at manager')

        self.worker_secret = generate_secret()
        platform = detect_platform()
        resp = self.manager.post(
            '/register-worker', json={
                'secret': self.worker_secret,
                'platform': platform,
                'supported_job_types': self.job_types,
            })

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

        self.fetch_task_task = asyncio.ensure_future(self.fetch_task(delay), loop=self.loop)

    def shutdown(self):
        """Gracefully shuts down any asynchronous tasks."""

        if self.fetch_task_task and not self.fetch_task_task.done():
            self._log.info('Cancelling task fetching task %s', self.fetch_task_task)
            self.fetch_task_task.cancel()

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
            resp = self.manager.post('/task',
                                     auth=(self.worker_id, self.worker_secret))
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
            self.register_task_update(task_status='active')
            ok = await self.trunner.execute(task_info, self)
            if ok:
                self.register_task_update(task_status='completed')
            else:
                self.register_task_update(task_status='failed')
        except Exception as ex:
            self._log.exception('Uncaught exception executing task %s' % self.task_id)
            try:
                self.queued_log_entries.append(traceback.format_exc())
                self.register_task_update(
                    task_status='failed',
                    activity='Uncaught exception: %s %s' % (type(ex).__name__, ex),
                )
            except:
                self._log.exception('While notifying manager of failure, another error happened.')
        finally:
            # Always schedule a new task run; after a little delay to not hammer the world
            # when we're in some infinite failure loop.
            self.schedule_fetch_task(3)

    def push_to_master(self):
        """Updates a task's status and activity.
        """

        # TODO Sybren: do this in a separate thread, as to not block the task runner.

        import requests

        self._log.info('Updating task %s with status %r and activity %r',
                       self.task_id, self.current_task_status, self.last_task_activity)

        payload = attr.asdict(self.last_task_activity)
        payload['task_status'] = self.current_task_status

        now = datetime.datetime.now()
        self.last_activity_push = now

        if self.queued_log_entries:
            payload['log'] = '\n'.join(self.queued_log_entries)
            self.queued_log_entries.clear()
            self.last_log_push = now

        resp = self.manager.post('/tasks/%s/update' % self.task_id,
                                 json=payload,
                                 auth=(self.worker_id, self.worker_secret))
        self._log.debug('Sent task %s update to manager', self.task_id)
        try:
            resp.raise_for_status()
        except requests.HTTPError as ex:
            self._log.error('Unable to send status update to manager, update is lost: %s', ex)

    def register_task_update(self, *,
                             task_status: str = None,
                             **kwargs):
        """Stores the task status and activity, and possibly sends to Flamenco Master.

        If the last update to Master was long enough ago, or the task status changed,
        the info is sent to Master. This way we can update command progress percentage
        hundreds of times per second, without worrying about network overhead.
        """

        # Update the current activity
        for key, value in kwargs.items():
            setattr(self.last_task_activity, key, value)

        task_status_changed = self.current_task_status != task_status
        self.current_task_status = task_status

        if task_status_changed:
            self._log.info('Task changed status to %s, pushing to master', task_status)
            self.push_to_master()
        elif datetime.datetime.now() - self.last_activity_push > PUSH_ACT_MAX_INTERVAL:
            self._log.info('More than %s since last activity update, pushing to master',
                           PUSH_ACT_MAX_INTERVAL)
            self.push_to_master()

    def register_log(self, log_entry):
        """Registers a log entry, and possibly sends all queued log entries to upstream Master."""

        from . import tz

        now = datetime.datetime.now(tz.tzutc()).isoformat()
        self.queued_log_entries.append('%s: %s' % (now, log_entry))

        if len(self.queued_log_entries) > PUSH_LOG_MAX_ENTRIES:
            self._log.info('Queued up more than %i log entries, pushing to master',
                           PUSH_LOG_MAX_ENTRIES)
            self.push_to_master()
        elif datetime.datetime.now() - self.last_log_push > PUSH_LOG_MAX_INTERVAL:
            self._log.info('More than %s since last log update, pushing to master',
                           PUSH_LOG_MAX_INTERVAL)
            self.push_to_master()


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
