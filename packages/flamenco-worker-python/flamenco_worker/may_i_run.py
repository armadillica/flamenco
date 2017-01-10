"""Polls the /may-i-run/{task-id} endpoint on the Manager."""

import asyncio
import datetime

import attr

from . import attrs_extra
from . import documents
from . import worker
from . import upstream


@attr.s
class MayIRun:
    manager = attr.ib(validator=attr.validators.instance_of(upstream.FlamencoManager),
                      repr=False)
    worker = attr.ib(validator=attr.validators.instance_of(worker.FlamencoWorker),
                     repr=False)
    poll_interval = attr.ib(validator=attr.validators.instance_of(datetime.timedelta))
    loop = attr.ib(validator=attr.validators.instance_of(asyncio.AbstractEventLoop))

    _log = attrs_extra.log('%s.MayIRun' % __name__)

    async def work(self):
        try:
            while True:
                await self.one_iteration()
                await asyncio.sleep(self.poll_interval.total_seconds())
        except asyncio.CancelledError:
            self._log.warning('Shutting down.')

    async def one_iteration(self):
        task_id = self.worker.active_task_id

        if not task_id:
            # self._log.debug('No current task')
            return

        if await self.may_i_run(task_id):
            self._log.debug('Current task may run')
            return

        self._log.warning('We have to stop task %s', task_id)
        await self.worker.stop_current_task()

    async def may_i_run(self, task_id: str) -> bool:
        """Asks the Manager whether we are still allowed to run the given task."""

        resp = await self.manager.get('/may-i-run/%s' % task_id, loop=self.loop)
        may_keep_running = documents.MayKeepRunningResponse(**resp.json())

        if not may_keep_running.may_keep_running:
            self._log.warning('Not allowed to keep running task %s: %s',
                              task_id, may_keep_running.reason)

        return may_keep_running.may_keep_running
