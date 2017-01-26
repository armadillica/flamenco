"""Commandline interface entry points."""

import argparse
import asyncio
import datetime
import logging
import logging.config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config',
                        help='Load this configuration file instead of the default files.')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show configuration before starting, '
                             'and asyncio task status at shutdown.')
    args = parser.parse_args()

    # Load configuration
    from . import config
    confparser = config.load_config(args.config, args.verbose)
    config.configure_logging(confparser)

    log = logging.getLogger(__name__)
    log.debug('Starting')

    # Patch AsyncIO
    from . import patch_asyncio
    patch_asyncio.patch_asyncio()

    # Construct the AsyncIO loop
    loop = construct_asyncio_loop()
    if args.verbose:
        log.debug('Enabling AsyncIO debugging')
        loop.set_debug(True)
    shutdown_future = loop.create_future()

    # Piece all the components together.
    from . import runner, worker, upstream, upstream_update_queue, may_i_run

    fmanager = upstream.FlamencoManager(
        manager_url=confparser.value('manager_url'),
    )

    tuqueue = upstream_update_queue.TaskUpdateQueue(
        db_fname=confparser.value('task_update_queue_db'),
        manager=fmanager,
        shutdown_future=shutdown_future,
    )
    trunner = runner.TaskRunner(
        shutdown_future=shutdown_future)

    fworker = worker.FlamencoWorker(
        manager=fmanager,
        trunner=trunner,
        tuqueue=tuqueue,
        job_types=confparser.value('job_types').split(),
        worker_id=confparser.value('worker_id'),
        worker_secret=confparser.value('worker_secret'),
        loop=loop,
        shutdown_future=shutdown_future,
        push_log_max_interval=confparser.interval_secs('push_log_max_interval_seconds'),
        push_log_max_entries=confparser.value('push_log_max_entries', int),
        push_act_max_interval=confparser.interval_secs('push_act_max_interval_seconds'),
    )

    mir = may_i_run.MayIRun(
        manager=fmanager,
        worker=fworker,
        poll_interval=confparser.interval_secs('may_i_run_interval_seconds'),
        loop=loop,
    )

    def shutdown(signum, stackframe):
        """Perform a clean shutdown."""

        # Raise an exception, so that the exception is bubbled upwards, until
        # the asyncio loop stops executing the current task. Only then can we
        # run things like loop.run_until_complete(mir_work_task).
        log.warning('Shutting down due to signal %i', signum)
        raise KeyboardInterrupt()

    # Shut down cleanly upon TERM signal
    import signal
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGUSR1, asyncio_report_tasks)

    # Start asynchronous tasks.
    asyncio.ensure_future(tuqueue.work(loop=loop))
    mir_work_task = asyncio.ensure_future(mir.work())

    try:
        loop.run_until_complete(fworker.startup())
        fworker.mainloop()
    except worker.UnableToRegisterError:
        # The worker will have logged something, we'll just shut down cleanly.
        pass
    except KeyboardInterrupt:
        shutdown_future.cancel()
        mir_work_task.cancel()
        loop.run_until_complete(mir_work_task)

        fworker.shutdown()

        async def stop_loop():
            log.info('Waiting to give tasks the time to stop gracefully')
            await asyncio.sleep(1)
            loop.stop()

        loop.run_until_complete(stop_loop())
    except:
        log.exception('Uncaught exception!')

    # Report on the asyncio task status
    if args.verbose:
        asyncio_report_tasks()

    log.warning('Closing asyncio loop')
    loop.close()
    log.warning('Flamenco Worker is shut down')


def asyncio_report_tasks(signum=0, stackframe=None):
    """Runs the garbage collector, then reports all AsyncIO tasks on the log.

    Can be used as signal handler.
    """

    log = logging.getLogger('%s.asyncio_report_tasks' % __name__)
    log.info('Logging all asyncio tasks.')

    all_tasks = asyncio.Task.all_tasks()
    count_done = sum(task.done() for task in all_tasks)

    if not len(all_tasks):
        log.info('No scheduled tasks')
    elif len(all_tasks) == count_done:
        log.info('All %i tasks are done.', len(all_tasks))
    else:
        log.info('%i tasks, of which %i are done.', len(all_tasks), count_done)

    import gc
    import traceback

    # Clean up circular references between tasks.
    gc.collect()

    for task_idx, task in enumerate(all_tasks):
        if not task.done():
            log.info('   task #%i: %s', task_idx, task)
            continue

        # noinspection PyBroadException
        try:
            res = task.result()
            log.info('   task #%i: %s result=%r', task_idx, task, res)
        except asyncio.CancelledError:
            # No problem, we want to stop anyway.
            log.info('   task #%i: %s cancelled', task_idx, task)
        except Exception:
            log.info('%s: resulted in exception: %s', task, traceback.format_exc())

        # for ref in gc.get_referrers(task):
        #     log.info('      - referred by %s', ref)

    log.info('Done logging.')


def construct_asyncio_loop() -> asyncio.AbstractEventLoop:
    # On Windows, the default event loop is SelectorEventLoop which does
    # not support subprocesses. ProactorEventLoop should be used instead.
    # Source: https://docs.python.org/3.5/library/asyncio-subprocess.html
    import sys

    if sys.platform == 'win32':
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()

    asyncio.set_event_loop(loop)
    return loop


if __name__ == '__main__':
    main()
