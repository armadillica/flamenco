import contextlib
import datetime
import pathlib
import unittest
from unittest import mock

from bson import ObjectId, tz_util
import werkzeug.exceptions as wz_exceptions

from abstract_flamenco_test import AbstractFlamencoTest

teststore = pathlib.Path(__file__).with_name('jwt_keys')


class JWTKeyStoreTest(unittest.TestCase):

    def test_self_test(self):
        from flamenco import jwt

        # One public key that belongs to the private key.
        store = jwt.JWTKeyStore()
        store.load_keys(teststore / 'test-private-1.pem', teststore / 'test-public-1.pem')
        self.assertTrue(store._self_test())

        # Two public keys, none matching the private key.
        store = jwt.JWTKeyStore()
        store.load_keys(teststore / 'test-private-1.pem', teststore / 'test-public-2.pem')
        self.assertFalse(store._self_test())

        # Two public keys, one matching the private key.
        store = jwt.JWTKeyStore()
        store.load_keys(teststore / 'test-private-2.pem', teststore / 'test-public-2.pem')
        self.assertTrue(store._self_test())


class JWTPublicKeyServeTest(AbstractFlamencoTest):
    def test_keys_usable(self):
        """The default keys we use for testing should be valid."""
        self.assertTrue(self.jwt.usable)

    def test_get_keys(self):
        expect_key = (teststore / 'test-public-2.pem').read_bytes()
        resp = self.get(self.url_for('flamenco.jwt.api.public_keys'))
        self.assertEqual(expect_key, resp.data)


class GenerateJWTTokenTest(AbstractFlamencoTest):
    def setUp(self):
        super().setUp()
        self.create_user(user_id=24 * 'f', roles={'flamenco-admin'}, token='fladmin-token')
        self.create_manager()

    def test_unauthenticated(self):
        resp = self.get(self.url_for('flamenco.jwt.api.generate_token', manager_id=self.mngr_id),
                        expected_status=403)
        token = resp.data.decode()
        self.assertFalse(self.jwt._test_token(str(self.mngr_id), token))

    def test_bearer_auth(self):
        resp = self.get(self.url_for('flamenco.jwt.api.generate_token', manager_id=self.mngr_id),
                        headers={'Authorization': 'Bearer fladmin-token'},
                        expected_status=200)
        token = resp.data.decode()
        self.assertTrue(self.jwt._test_token(str(self.mngr_id), token))

    def test_session_auth_bad_hmac(self):
        from flamenco.jwt import api

        with self.app.test_request_context(query_string={
            'expires': '2019-01-02T15:04:05Z',
            'hmac': '12345',
        }):
            self.login_api_as(ObjectId(24 * 'f'), ['flamenco-admin'])
            with self.assertRaises(wz_exceptions.Unauthorized) as ex:
                api.generate_token(str(self.mngr_id))

        self.assertEqual('Bad HMAC', ex.exception.description)

    @contextlib.contextmanager
    def valid_request_context(self, **kwargs):
        expires = '2019-01-02T15:04:05Z'

        with self.app.app_context():
            hasher = self.mmngr.hasher(self.mngr_id)
        hasher.update(f'{expires}-{self.mngr_id}'.encode())
        hmac = hasher.hexdigest()

        with self.app.test_request_context(
                **kwargs,
                query_string={'expires': expires, 'hmac': hmac}):
            yield

    def test_session_auth_bad_expires(self):
        from flamenco.jwt import api

        with self.valid_request_context():
            self.login_api_as(ObjectId(24 * 'f'), ['flamenco-admin'])
            with self.assertRaises(wz_exceptions.Unauthorized) as ex, \
                    mock.patch('flamenco.jwt.api.utcnow') as mock_utcnow:
                mock_utcnow.return_value = datetime.datetime(year=2019, month=1, day=2,
                                                             hour=15, minute=4, second=6,
                                                             tzinfo=tz_util.utc)
                api.generate_token(str(self.mngr_id))
        self.assertEqual('Link expired', ex.exception.description)

    def test_session_auth_expires_too_far_future(self):
        from flamenco.jwt import api

        with self.valid_request_context():
            self.login_api_as(ObjectId(24 * 'f'), ['flamenco-admin'])
            with self.assertRaises(wz_exceptions.Unauthorized) as ex, \
                    mock.patch('flamenco.jwt.api.utcnow') as mock_utcnow:
                mock_utcnow.return_value = datetime.datetime(year=2019, month=1, day=2,
                                                             hour=14, minute=4, second=5,
                                                             tzinfo=tz_util.utc)
                api.generate_token(str(self.mngr_id))
        self.assertEqual('Link too far in the future', ex.exception.description)

    def test_session_auth_happy(self):
        from flamenco.jwt import api

        with self.valid_request_context():
            self.login_api_as(ObjectId(24 * 'f'), ['flamenco-admin'])
            with mock.patch('flamenco.jwt.api.utcnow') as mock_utcnow:
                mock_utcnow.return_value = datetime.datetime(year=2019, month=1, day=2,
                                                             hour=15, minute=3, second=0,
                                                             tzinfo=tz_util.utc)
                resp = api.generate_token(str(self.mngr_id))

        token = resp.data.decode('utf8')
        self.assertEqual(200, resp.status_code)
        self.assertTrue(self.jwt._test_token(str(self.mngr_id), token))
        self.assertNotIn('Access-Control-Allow-Origin', resp.headers,
                         'CORDS headers should only be in the response if Origin header was sent')

    def test_cors_headers(self):
        from flamenco.jwt import api

        with self.valid_request_context(headers={
            'Origin': 'http://jemoeder/',
        }):
            self.login_api_as(ObjectId(24 * 'f'), ['flamenco-admin'])
            with mock.patch('flamenco.jwt.api.utcnow') as mock_utcnow:
                mock_utcnow.return_value = datetime.datetime(year=2019, month=1, day=2,
                                                             hour=15, minute=3, second=0,
                                                             tzinfo=tz_util.utc)
                resp = api.generate_token(str(self.mngr_id))

        token = resp.data.decode('utf8')
        self.assertEqual(200, resp.status_code)
        self.assertTrue(self.jwt._test_token(str(self.mngr_id), token))
        self.assertEqual('http://jemoeder/', resp.headers['Access-Control-Allow-Origin'])
        self.assertEqual('true', resp.headers['Access-Control-Allow-Credentials'])
