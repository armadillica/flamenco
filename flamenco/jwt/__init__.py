"""JSON Web Token functionality."""

import datetime
import logging
import pathlib
import typing

from bson import ObjectId

import jwt.exceptions

log = logging.getLogger(__name__)


class JWTKeyStore:
    """Store for one private key and multiple public keys.

    The private key is used to sign JWT tokens. The public keys are offered on
    a publicly-available endpoint so that they can be downloaded.

    The private and public keys should reside in a single file each (so one file
    with the private key, and one file with all public keys concatenated).
    """

    def __init__(self) -> None:
        self.token_expiry = datetime.timedelta(hours=4)

        self._private_key_path = None  # type: typing.Optional[pathlib.Path]
        self._public_keys_path = None  # type: typing.Optional[pathlib.Path]

        self._private_key = b''
        self._public_keys = b''
        self._public_keys_mtime = ''

        self._usable = False

    def load_keys(self, private_key_path: pathlib.Path, public_keys_path: pathlib.Path) -> None:
        """Loads keys from disk.

        Can also be used to re-load keys after they changed.
        """

        log.info('Reading private key from %s', private_key_path)
        self._private_key = private_key_path.read_bytes().replace(b'\r\n', b'\n')

        log.info('Reading public keys from %s', public_keys_path)
        self._public_keys = public_keys_path.read_bytes().replace(b'\r\n', b'\n')

        self._private_key_path = private_key_path
        self._public_keys_path = public_keys_path

        st_mtime = public_keys_path.stat().st_mtime
        mtime = datetime.datetime.fromtimestamp(st_mtime)
        self._public_keys_mtime = mtime.isoformat(timespec='seconds')
        log.info('Public keys mtime is %s', self._public_keys_mtime)

        self._usable = bool(self.token_expiry is not None
                            and len(self._private_key)
                            and len(self._public_keys)
                            and self._self_test())

    def reload_keys(self) -> None:
        if self._private_key_path is None or self._public_keys_path is None:
            raise ValueError('unable to reload keys that have never been loaded')
        self.load_keys(self._private_key_path, self._public_keys_path)

    @property
    def usable(self) -> bool:
        """Whether the keys are usable."""
        return self._usable

    @property
    def public_keys(self) -> bytes:
        """Return the loaded public keys."""
        return self._public_keys

    @property
    def public_keys_last_modified(self) -> str:
        """Return a string indicating the last modification time of the keys."""
        return self._public_keys_mtime

    def _self_test(self) -> bool:
        """Try signing a token with our private key, and verify with a public key.

        Logs a warning if none of the public keys can verify the token.

        :return: True if we have a public key for our private key. False
            if we have no public key or none of them match our private key.
        """

        manager_id = 24 * '1'
        token = self.generate_key_for_manager(ObjectId(manager_id), ObjectId(24 * '2'))

        # Split the public key bytes into separate keys.
        sep = b'-----END PUBLIC KEY-----\n'
        keyparts = self._public_keys.split(sep)
        pubkeys = [part + sep for part in keyparts if part]

        for index, pubkey in enumerate(pubkeys):
            log.debug('Trying public key #%d:\n%s', index + 1, pubkey.decode('ascii'))
            try:
                jwt.decode(token, pubkey, algorithms=['ES256'], audience=manager_id)
            except jwt.exceptions.InvalidSignatureError as ex:
                log.debug('Public key #%d does not match our private key: %s', index + 1, ex)
                continue
            except jwt.exceptions.PyJWTError as ex:
                log.warning('Could not decode with public key #%d: %s', index + 1, ex)
                continue

            log.debug('Public key #%d matches our private key', index + 1)
            break
        else:
            log.error('None of my public keys match my private key!')
            return False

        return True

    def generate_key_for_manager(self, manager_id: ObjectId, user_id: ObjectId) -> str:
        """Generates a key for the current user and the given Manager."""

        now = datetime.datetime.utcnow()
        expiry = now + self.token_expiry

        claims = {
            'aud': str(manager_id),  # Flamenco Manager the key is generated for.
            'exp': expiry.timestamp(),
            'sub': str(user_id),  # The ObjectID of the user identified by this token.
            'iat': now.timestamp(),
        }
        token = jwt.encode(claims, self._private_key, algorithm='ES256')
        return token.decode('ascii')


def setup_app(app):
    from . import api

    api.setup_app(app)
