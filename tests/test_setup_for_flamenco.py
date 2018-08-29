import bson

import pillarsdk

import pillar.tests.common_test_data as ctd
from pillar.tests import AbstractPillarTest
from abstract_flamenco_test import AbstractFlamencoTest


class TaskWorkflowTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)
        self.project_id, _ = self.ensure_project_exists()
        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')

    def test_custom_properties(self):
        """Projects should get their properties dict."""

        with self.app.test_request_context():
            proj_coll = self.app.data.driver.db['projects']
            project = proj_coll.find_one({'_id': self.project_id})
            aprops = project['extension_props']['flamenco']
            self.assertIsInstance(aprops, dict)

    def test_saving_api(self):
        """Ensures that Eve accepts a Flamenco project as valid."""

        import pillar.api.utils

        url = '/api/projects/%s' % self.project_id

        resp = self.get(url)
        proj = resp.json

        put_proj = pillar.api.utils.remove_private_keys(proj)

        self.put(url,
                 json=put_proj,
                 auth_token='token',
                 headers={'If-Match': proj['_etag']})


class SetupForFlamencoThroughWebInterfaceTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        super().setUp(**kwargs)

        overrides = {'_id': bson.ObjectId(24 * 'b'),
                     'url': 'fresh-project',
                     'picture_header': None,
                     'picture_square': None}
        self.create_project_with_admin(24 * 'a',
                                       {'subscriber', 'flamenco-user'},
                                       project_overrides=overrides)
        self.create_valid_auth_token(24 * 'a', 'admin-token')
        self.project_id, self.proj = AbstractPillarTest.ensure_project_exists(self, overrides)
        self.sdk_proj = pillarsdk.Project(self.proj)

        self.assertFalse(self.flamenco.is_flamenco_project(self.sdk_proj))

    def ensure_project_exists(self, project_overrides=None):
        # Ensure that a project exists that is _not_ set up for Flamenco.
        return AbstractPillarTest.ensure_project_exists(self, project_overrides)

    def test_setup_through_web(self):
        self.do_setup_for_flamenco()

        # Test that the project is set up for Flamenco and has a Manager assigned.
        # The Manager should have been created too.
        new_proj = self.get(f'/api/projects/{self.project_id}', auth_token='admin-token').json
        self.assertTrue(self.flamenco.is_flamenco_project(pillarsdk.Project(new_proj)))

        man_man = self.flamenco.manager_manager
        with self.app.test_request_context():
            project_managers = man_man.managers_for_project(self.project_id)
        self.assertEqual(1, len(project_managers))
        manager_id = project_managers[0]

        self.assertManagerAssigned(manager_id)

    def test_setup_autoassign_manager(self):
        man_man = self.flamenco.manager_manager

        with self.app.test_request_context():
            from pillar.api.utils.authentication import force_cli_user
            force_cli_user()
            _, mngr_doc, _ = man_man.create_new_manager('pre-existing manager', '',
                                                        bson.ObjectId(24 * 'a'))

        self.do_setup_for_flamenco()

        # Test that the project is set up for Flamenco and has a Manager assigned.
        new_proj = self.get(f'/api/projects/{self.project_id}', auth_token='admin-token').json
        self.assertTrue(self.flamenco.is_flamenco_project(pillarsdk.Project(new_proj)))

        with self.app.test_request_context():
            project_managers = man_man.managers_for_project(self.project_id)

        expected_manager_id = mngr_doc['_id']
        self.assertEqual([expected_manager_id], project_managers)
        self.assertManagerAssigned(expected_manager_id)

    def assertManagerAssigned(self, manager_id):
        import pillar.auth

        man_man = self.flamenco.manager_manager
        flauth = self.flamenco.auth
        with self.app.test_request_context():
            pillar.auth.login_user('admin-token', load_from_db=True)
            self.assertTrue(flauth.current_user_may(flauth.Actions.USE, self.project_id))
            self.assertTrue(man_man.user_is_owner(mngr_doc_id=manager_id))

    def do_setup_for_flamenco(self):
        import pillar.auth
        from flamenco import routes

        with self.app.test_request_context():
            pillar.auth.login_user('admin-token', load_from_db=True)
            self.sdk_proj.allowed_methods = ['GET', 'PUT', 'DELETE']
            routes.setup_for_flamenco(self.sdk_proj)
