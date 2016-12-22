import asyncio

import attr

from . import attrs_extra
from . import upstream

# All durations/delays/etc are in seconds.
FETCH_TASK_FAILED_RETRY_DELAY = 10  # when we failed obtaining a task
FETCH_TASK_EMPTY_RETRY_DELAY = 5  # when there are no tasks to perform


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
        default=None,
        init=False,
        validator=attr.validators.optional(attr.validators.instance_of(asyncio.Task)))

    _log = attrs_extra.log('%s.FlamencoWorker' % __name__)

    def startup(self):
        self._log.info('Starting up')

        if not self.worker_id or not self.worker_secret:
            self.register_at_manager()

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
        self.schedule_fetch_task()
        self.loop.run_forever()

    def schedule_fetch_task(self, delay=0):
        """Schedules a task fetch.

        If a task fetch was already queued, that one is cancelled.

        :param delay: delay in seconds, after which the task fetch will be performed.
        """

        if self.fetch_task_task:
            self.fetch_task_task.cancel()

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
        task_id = task_info['_id']
        self._log.info('Received task: %s', task_id)
        self._log.debug('Received task: %s', task_info)

        try:
            await self.trunner.execute(task_info, self)
        except Exception as ex:
            self._log.exception('Uncaught exception executing task %s' % task_id)
            self.send_task_update(
                task_id,
                'failed',
                'Uncaught exception: %s' % ex
            )
        finally:
            # Always schedule a new task run.
            self.schedule_fetch_task(0)

    def send_task_update(self, task_id, new_activity_descr: str = None,
                         task_status: str = None):
        """Updates a task's status and activity description."""

        import requests

        self._log.info('Updating task %s with new status %r and activity %r',
                       task_id, task_status, new_activity_descr)

        payload = {'activity_descr': new_activity_descr}
        if task_status:
            payload['task_status'] = task_status

        resp = self.manager.post('/tasks/%s/update' % task_id,
                                 json=payload,
                                 auth=(self.worker_id, self.worker_secret))
        self._log.debug('Sent task %s update to manager', task_id)
        try:
            resp.raise_for_status()
        except requests.HTTPError as ex:
            self._log.error('Unable to send status update to manager, update is lost: %s', ex)


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
