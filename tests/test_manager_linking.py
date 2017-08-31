import datetime
import mock

import bson
from bson import tz_util

from abstract_flamenco_test import AbstractFlamencoTest

secret_hex = 'e0560736e15b1e02311a49961505a0d39181fd8ae57d368ee7b890e205d48691'
secret_bin = b'\xe0V\x076\xe1[\x1e\x021\x1aI\x96\x15\x05\xa0\xd3\x91\x81\xfd' \
             b'\x8a\xe5}6\x8e\xe7\xb8\x90\xe2\x05\xd4\x86\x91'


class ManagerLinkTest(AbstractFlamencoTest):
    """Test for linking Managers to this Server."""

    def setUp(self, **kwargs):
        super().setUp(**kwargs)
        self.enter_app_context()

    def _normal_exchange(self) -> bson.ObjectId:
        resp = self.post('/api/flamenco/managers/link/exchange',
                         json={'key': secret_hex})
        return bson.ObjectId(resp.get_json()['identifier'])

    def test_exchange_secret_key_happy(self):
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

        coll = self.flamenco.db('manager_linking_keys')
        self.assertEqual(0, coll.count())

    def test_exchange_secret_key_no_key(self):
        self.post('/api/flamenco/managers/link/exchange',
                  json={},
                  expected_status=400)

        coll = self.flamenco.db('manager_linking_keys')
        self.assertEqual(0, coll.count())
