"""Writes configuration to a config file in the home directory."""

import collections
import configparser
import os.path
import logging

HOME_CONFIG_FILE = os.path.expanduser('~/.flamenco-worker.cfg')
GLOBAL_CONFIG_FILE = 'flamenco-worker.cfg'
CONFIG_SECTION = 'flamenco-worker'

DEFAULT_CONFIG = {
    'flamenco-worker': collections.OrderedDict([
        ('manager_url', 'http://flamenco-manager/'),
        ('job_types', 'sleep blender_render_simple'),
        ('task_update_queue_db', 'flamenco-worker.db'),
        ('worker_id', ''),
        ('worker_secret', ''),
    ])
}

log = logging.getLogger(__name__)


def merge_with_home_config(new_conf: dict):
    """Updates the home configuration file with the given config dict."""

    confparser = configparser.ConfigParser()
    confparser.read_dict({CONFIG_SECTION: {}})
    confparser.read(HOME_CONFIG_FILE, encoding='utf8')

    for key, value in new_conf.items():
        confparser.set(CONFIG_SECTION, key, value)

    tmpname = HOME_CONFIG_FILE + '~'
    log.debug('Writing configuration file to %s', tmpname)
    with open(tmpname, mode='wt', encoding='utf8') as outfile:
        confparser.write(outfile)

    log.debug('Moving configuration file to %s', HOME_CONFIG_FILE)
    os.replace(tmpname, HOME_CONFIG_FILE)

    log.info('Updated configuration file %s', HOME_CONFIG_FILE)


def load_config(config_file: str = None,
                show_effective_config: bool = False) -> configparser.ConfigParser:
    """Loads one or more configuration files."""

    confparser = configparser.ConfigParser()
    confparser.read_dict(DEFAULT_CONFIG)

    if config_file:
        log.info('Loading configuration from %s', config_file)
        loaded = confparser.read(config_file, encoding='utf8')
    else:
        config_files = [GLOBAL_CONFIG_FILE, HOME_CONFIG_FILE]
        log.info('Loading configuration from %s', ', '.join(config_files))
        loaded = confparser.read(config_files, encoding='utf8')

    log.info('Succesfully loaded: %s', loaded)

    if show_effective_config:
        import sys
        log.info('Effective configuration:')
        to_show = configparser.ConfigParser()
        to_show.read_dict(confparser)
        if to_show.get(CONFIG_SECTION, 'worker_secret'):
            to_show.set(CONFIG_SECTION, 'worker_secret', '-hidden-')
        to_show.write(sys.stderr)

    return confparser
