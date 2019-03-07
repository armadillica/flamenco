import pathlib
import unittest

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
