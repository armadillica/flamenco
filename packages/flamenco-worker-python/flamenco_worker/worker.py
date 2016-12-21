import attr

from . import attrs_extra
from . import upstream


@attr.s
class FlamencoWorker:
    manager = attr.ib(validator=attr.validators.instance_of(upstream.FlamencoManager))
    job_types = attr.ib(validator=attr.validators.instance_of(list))
    worker_id = attr.ib(validator=attr.validators.instance_of(str))
    worker_secret = attr.ib(validator=attr.validators.instance_of(str))

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
