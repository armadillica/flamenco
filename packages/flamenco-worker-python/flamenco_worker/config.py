"""Writes configuration to a config file in the home directory."""

import configparser
import os.path
import logging

HOME_CONFIG_FILE = os.path.expanduser('~/.flamenco-worker.cfg')
GLOBAL_CONFIG_FILE = 'flamenco-worker.cfg'
CONFIG_SECTION = 'flamenco-worker'

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
