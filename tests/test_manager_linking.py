import datetime

import bson
from bson import tz_util

from abstract_flamenco_test import AbstractFlamencoTest

secret_hex = 'e0560736e15b1e02311a49961505a0d39181fd8ae57d368ee7b890e205d48691'
secret_bin = b'\xe0V\x076\xe1[\x1e\x021\x1aI\x96\x15\x05\xa0\xd3\x91\x81\xfd' \
             b'\x8a\xe5}6\x8e\xe7\xb8\x90\xe2\x05\xd4\x86\x91'


class ManagerLinkTest(AbstractFlamencoTest):
    """Test for linking Managers to this Server."""

    def _normal_exchange(self) -> bson.ObjectId:
        resp = self.post('/api/flamenco/managers/link/exchange',
                         json={'key': secret_hex})
        return bson.ObjectId(resp.get_json()['identifier'])

    def test_exchange_secret_key_happy(self):
        self.enter_app_context()
        before_request = datetime.datetime.now(tz=tz_util.utc)

        ident = self._normal_exchange()

        coll = self.flamenco.db('manager_linking_keys')
        db_key = coll.find_one({'_id': ident})

        self.assertIsNotNone(db_key, 'Key should be stored in the database!')
        self.assertEqual(db_key['secret_key'], secret_bin)

        # The expiry of the stored key should be after 'before_request', but before
        # now + 5 hours.
        after_request = datetime.datetime.now(tz=tz_util.utc)
        self.assertLess(before_request, db_key['remove_after'])
        self.assertLess(db_key['remove_after'], after_request + datetime.timedelta(hours=5))

    def test_exchange_secret_key_malformed_key(self):
        self.post('/api/flamenco/managers/link/exchange',
                  json={'key': secret_hex[:-1]},
                  expected_status=400)

        with self.app.app_context():
            coll = self.flamenco.db('manager_linking_keys')
            self.assertEqual(0, coll.count_documents({}))

    def test_exchange_secret_key_no_key(self):
        self.post('/api/flamenco/managers/link/exchange',
                  json={},
                  expected_status=400)

        with self.app.app_context():
            coll = self.flamenco.db('manager_linking_keys')
            self.assertEqual(0, coll.count_documents({}))

    def test_reset_auth_token_happy(self):
        import secrets

        from flamenco.managers.linking_routes import _compute_hash

        with self.app.app_context():
            mngr_doc, account, old_token_info = self.create_manager_service_account()
            manager_id = mngr_doc['_id']

            # Exchange two keys
            ident = self._normal_exchange()
            self.post('/api/flamenco/managers/link/exchange', json={'key': 'aabbccddeeff'})

            coll = self.flamenco.db('manager_linking_keys')
            self.assertEqual(2, coll.count_documents({}))

            # Bind them to the same Manager
            coll.update_many({}, {'$set': {'manager_id': manager_id}})

        # Check that both secret keys are gone after requesting an auth token reset.
        padding = secrets.token_hex(32)
        msg = f'{padding}-{ident}-{manager_id}'
        mac = _compute_hash(secret_bin, msg.encode('ascii'))
        payload = {
            'manager_id': str(manager_id),
            'identifier': str(ident),
            'padding': padding,
            'hmac': mac,
        }
        resp = self.post('/api/flamenco/managers/link/reset-token', json=payload)

        # Test the token by getting the manager document.
        token_info = resp.get_json()
        token = token_info['token']
        self.get(f'/api/flamenco/managers/{manager_id}', auth_token=token)

        # The old token shouldn't work any more.
        self.get(f'/api/flamenco/managers/{manager_id}',
                 auth_token=old_token_info['token'],
                 expected_status=403)
