"""Commandline interface entry points."""

import argparse
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

    from . import worker, upstream

    fmanager = upstream.FlamencoManager(
        manager_url=confparser.get(config.CONFIG_SECTION, 'manager_url'),
    )

    fworker = worker.FlamencoWorker(
        manager=fmanager,
        job_types=confparser.get(config.CONFIG_SECTION, 'job_types').split(),
        worker_id=confparser.get(config.CONFIG_SECTION, 'worker_id'),
        worker_secret=confparser.get(config.CONFIG_SECTION, 'worker_secret'),
    )
    try:
        fworker.startup()
        fworker.mainloop()
    except:
        log.exception('Uncaught exception!')
    log.warning('Shutting down')


if __name__ == '__main__':
    main()
