"""Commandline interface entry points."""

import argparse
import asyncio
import logging
import logging.config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config',
                        help='Load this configuration file instead of the default files.')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Log less (only WARNING and more severe).')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Log more (DEBUG and more severe).')
    args = parser.parse_args()

    # Set up logging
    if args.quiet:
        level = 'WARNING'
    elif args.verbose:
        level = 'DEBUG'
    else:
        level = 'INFO'
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'default': {'format': '%(asctime)-15s %(levelname)8s %(name)s %(message)s'}
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'stream': 'ext://sys.stderr',
            }
        },
        'loggers': {
            'flamenco_worker': {'level': level},
        },
        'root': {
            'level': 'WARNING',
            'handlers': [
                'console',
            ],
        }
    })

    log = logging.getLogger(__name__)
    log.debug('Starting')

    # Load configuration
    from . import config
    confparser = config.load_config(args.config, args.verbose)

    # Construct the AsyncIO loop
    loop = asyncio.get_event_loop()
    if args.verbose:
        log.debug('Enabling AsyncIO debugging')
        loop.set_debug(True)
    shutdown_future = loop.create_future()

    # Piece all the components together.
    from . import runner, worker, upstream

    fmanager = upstream.FlamencoManager(
        manager_url=confparser.get(config.CONFIG_SECTION, 'manager_url'),
    )

    trunner = runner.TaskRunner(
        shutdown_future=shutdown_future)

    fworker = worker.FlamencoWorker(
        manager=fmanager,
        trunner=trunner,
        job_types=confparser.get(config.CONFIG_SECTION, 'job_types').split(),
        worker_id=confparser.get(config.CONFIG_SECTION, 'worker_id'),
        worker_secret=confparser.get(config.CONFIG_SECTION, 'worker_secret'),
        loop=loop,
        shutdown_future=shutdown_future,
    )

    try:
        fworker.startup()
        fworker.mainloop()
    except KeyboardInterrupt:
        log.warning('Shutting down due to keyboard interrupt')
        shutdown_future.cancel()
        fworker.shutdown()

        async def stop_loop():
            log.info('Waiting to give tasks the time to stop gracefully')
            await asyncio.sleep(2)
            loop.stop()
        loop.run_until_complete(stop_loop())
    except:
        log.exception('Uncaught exception!')
    log.warning('Shutting down')


if __name__ == '__main__':
    main()
