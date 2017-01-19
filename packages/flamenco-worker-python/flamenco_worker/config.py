"""Writes configuration to a config file in the home directory."""

import collections
import configparser
import datetime
import os.path
import logging

from . import worker

HOME_CONFIG_FILE = os.path.expanduser('~/.flamenco-worker.cfg')
GLOBAL_CONFIG_FILE = 'flamenco-worker.cfg'
CONFIG_SECTION = 'flamenco-worker'

DEFAULT_CONFIG = {
    'flamenco-worker': collections.OrderedDict([
        ('manager_url', 'http://flamenco-manager/'),
        ('job_types', 'sleep blender_render_simple'),
        ('task_update_queue_db', 'flamenco-worker.db'),
        ('may_i_run_interval_seconds', '5'),
        ('worker_id', ''),
        ('worker_secret', ''),

        # All intervals in seconds
        ('push_log_max_interval_seconds', str(worker.PUSH_LOG_MAX_INTERVAL.total_seconds())),
        ('push_log_max_entries', str(worker.PUSH_LOG_MAX_ENTRIES)),
        ('push_act_max_interval_seconds', str(worker.PUSH_ACT_MAX_INTERVAL.total_seconds())),
    ])
}

log = logging.getLogger(__name__)


class ConfigParser(configparser.ConfigParser):
    """ConfigParser that can easily get values from our default config section."""

    _DEFAULT_INTERPOLATION = configparser.ExtendedInterpolation()

    def value(self, key, valtype: type=str):
        return valtype(self.get(CONFIG_SECTION, key))

    def interval_secs(self, key) -> datetime.timedelta:
        """Returns the configuration value as timedelta."""

        secs = self.value(key, float)
        return datetime.timedelta(seconds=secs)


def merge_with_home_config(new_conf: dict):
    """Updates the home configuration file with the given config dict."""

    confparser = ConfigParser()
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
                show_effective_config: bool = False) -> ConfigParser:
    """Loads one or more configuration files."""

    # Logging and the default interpolation of configparser both use the
    # same syntax for variables. To make it easier to work with, we use
    # another interpolation for config files, so they now use ${loglevel}
    # whereas logging still uses %(levelname)s.
    confparser = ConfigParser()
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
        to_show = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation()
        )
        to_show.read_dict(confparser)
        if to_show.get(CONFIG_SECTION, 'worker_secret'):
            to_show.set(CONFIG_SECTION, 'worker_secret', '-hidden-')
        to_show.write(sys.stderr)

    return confparser


def configure_logging(confparser: configparser.ConfigParser):
    import logging.config

    logging.config.fileConfig(confparser, disable_existing_loggers=True)
    logging.captureWarnings(capture=True)
