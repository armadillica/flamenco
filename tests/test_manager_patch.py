from abstract_flamenco_test import AbstractFlamencoTest


class ManagerEditTest(AbstractFlamencoTest):
    """Test for editing Managers from the web via PATCH."""

    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']
        self.mngr_doc = mngr_doc
        self.mngr_token = token['token']

        self.create_user(user_id=24 * 'e',
                         roles={'subscriber', 'flamenco-user'},
                         groups=[self.mngr_doc['owner']],
                         token='owner-token')

        self.create_user(user_id=24 * 'a',
                         roles={'subscriber', 'flamenco-user'},
                         token='other-flamuser-token')

    def test_patch_edit_from_web(self):
        patch = {'op': 'edit-from-web',
                 'name': 'Новое имя менеджера',
                 'description': '"New manager name" in Russian', }
        self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                   auth_token='owner-token',
                   json=patch,
                   expected_status=204)

        db_mngr = self.fetch_manager_from_db(self.mngr_id)
        self.assertIsNotNone(db_mngr)

        self.assertEqual(patch['name'], db_mngr['name'])
        self.assertEqual(patch['description'], db_mngr['description'])

    def test_patch_edit_from_web_validation_errors(self):
        patch = {'op': 'edit-from-web',
                 'name': 100 * 'Новое имя менеджера',
                 'description': 100 * '"New manager name" in Russian', }
        resp = self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                          auth_token='owner-token',
                          json=patch,
                          expected_status=422).json()
        self.assertIn('name', resp['_errors'])
        self.assertIn('description', resp['_errors'])

        db_mngr = self.fetch_manager_from_db(self.mngr_id)
        self.assertIsNotNone(db_mngr)

        self.assertEqual(self.mngr_doc['name'], db_mngr['name'])
        self.assertEqual(self.mngr_doc['description'], db_mngr['description'])

    def test_patch_edit_from_web_other_user(self):
        patch = {'op': 'edit-from-web',
                 'name': 'Новое имя менеджера',
                 'description': '"New manager name" in Russian', }
        self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                   auth_token='other-flamuser-token',
                   json=patch,
                   expected_status=403)

        db_mngr = self.fetch_manager_from_db(self.mngr_id)
        self.assertIsNotNone(db_mngr)

        self.assertEqual(self.mngr_doc['name'], db_mngr['name'])
        self.assertEqual(self.mngr_doc['description'], db_mngr['description'])
