"""Commandline interface entry points."""

import argparse
import collections
import configparser
import logging
import logging.config
import os

DEFAULT_CONFIG = {
    'flamenco-worker': collections.OrderedDict([
        ('manager_url', 'http://flamenco-manager/'),
        ('job_types', 'sleep blender_render_simple'),
        ('worker_id', ''),
        ('worker_secret', ''),
    ])
}


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
    confparser = configparser.ConfigParser()
    confparser.read_dict(DEFAULT_CONFIG)

    if args.config:
        log.info('Loading configuration from %s', args.config)
        confparser.read(args.config, encoding='utf8')
    else:
        from . import config as config_module
        config_files = [config_module.GLOBAL_CONFIG_FILE,
                        config_module.HOME_CONFIG_FILE]
        log.info('Loading configuration from %s', ', '.join(config_files))
        confparser.read(config_files, encoding='utf8')

    from .config import CONFIG_SECTION
    if args.verbose:
        import sys
        log.info('Effective configuration:')
        to_show = configparser.ConfigParser()
        to_show.read_dict(confparser)
        if to_show.get(CONFIG_SECTION, 'worker_secret'):
            to_show.set(CONFIG_SECTION, 'worker_secret', '-hidden-')
        to_show.write(sys.stderr)

    from . import worker, upstream

    fmanager = upstream.FlamencoManager(
        manager_url=confparser.get(CONFIG_SECTION, 'manager_url'),
    )

    fworker = worker.FlamencoWorker(
        manager=fmanager,
        job_types=confparser.get(CONFIG_SECTION, 'job_types').split(),
        worker_id=confparser.get(CONFIG_SECTION, 'worker_id'),
        worker_secret=confparser.get(CONFIG_SECTION, 'worker_secret'),
    )
    try:
        fworker.startup()
        fworker.mainloop()
    except:
        log.exception('Uncaught exception!')
    log.warning('Shutting down')


if __name__ == '__main__':
    main()
