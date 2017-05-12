# -*- encoding: utf-8 -*-

import bson

from pillar.tests import common_test_data as ctd
from pillar.api.utils.authentication import force_cli_user

from abstract_flamenco_test import AbstractFlamencoTest


class AbstractAccessTest(AbstractFlamencoTest):
    def _create_project(self, project_name, token) -> dict:
        resp = self.post('/api/p/create',
                         headers={'Authorization': self.make_header(token)},
                         expected_status=201,
                         data={'project_name': project_name})
        return resp.json()

    def _create_user_and_project(self, roles, user_id='cafef00df00df00df00df00d', token='token',
                                 project_name='Prøject El Niño') -> dict:
        self.create_user(user_id, roles, token=token)
        return self._create_project(project_name, token)


class AccessTest(AbstractAccessTest):
    """Creates a manager, job and tasks, to check access by different types of users.

    There are also separate access tests in other test cases.
    """

    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from flamenco import current_flamenco

        # Main project will have a manager, job, and tasks.
        mngr_doc, _, token = self.create_manager_service_account()

        self.mngr_id = mngr_doc['_id']
        self.mngr_doc = mngr_doc
        self.mngr_token = token['token']

        with self.app.test_request_context():
            force_cli_user()
            job = self.jmngr.api_create_job(
                'test job',
                'Wörk wørk w°rk.',
                'sleep',
                {
                    'frames': '12-18, 20-22',
                    'chunk_size': 3,
                    'time_in_seconds': 3,
                },
                self.proj_id,
                ctd.EXAMPLE_PROJECT_OWNER_ID,
                self.mngr_id,
            )
            self.job_id = job['_id']

            tasks_coll = current_flamenco.db('tasks')
            self.tasks_for_job = list(tasks_coll.find({'job': self.job_id}))

        # Another project, also with manager, job, and tasks.
        proj2_owner_id = 24 * 'a'
        self.proj2 = self._create_user_and_project(user_id=proj2_owner_id,
                                                   roles={'subscriber'},
                                                   project_name='Prøject 2',
                                                   token='token-proj2-owner')
        self.proj2_id = self.proj2['_id']

        mngr_doc, _, token = self.create_manager_service_account(
            email='manager2@example.com', name='manager 2'
        )
        self.mngr2_id = mngr_doc['_id']
        self.mngr2_doc = mngr_doc
        self.mngr2_token = token['token']

        with self.app.test_request_context():
            force_cli_user()

            job = self.jmngr.api_create_job(
                'test job 2',
                'Wörk² wørk² w°rk².',
                'sleep',
                {
                    'frames': '12-18, 20-22',
                    'chunk_size': 3,
                    'time_in_seconds': 3,
                },
                self.proj2_id,
                proj2_owner_id,
                self.mngr2_id,
            )
            self.job2_id = job['_id']

    def test_manager_account_access(self):
        """Should have access to own job and tasks, but not project or other managers."""

        from pillar.api.utils import remove_private_keys

        # Own manager doc should be gettable, but other one should not.
        own_url = '/api/flamenco/managers/%s' % self.mngr_id
        own_doc = self.get(own_url,
                           expected_status=200,
                           auth_token=self.mngr_token).json()
        other_url = '/api/flamenco/managers/%s' % self.mngr2_id
        self.get(other_url,
                 expected_status=404,
                 auth_token=self.mngr_token)

        # Managers may not create new managers.
        new_doc = remove_private_keys(own_doc)
        self.post('/api/flamenco/managers', json=new_doc,
                  expected_status=403,
                  auth_token=self.mngr_token)

        # Manager docs should not be modified.
        self.put(own_url, json=remove_private_keys(own_doc),
                 headers={'If-Match': own_doc['_etag']},
                 expected_status=403,
                 auth_token=self.mngr_token)
        self.delete(own_url,
                    expected_status=405,
                    auth_token=self.mngr_token)
        self.put(other_url, json=remove_private_keys(own_doc),
                 expected_status=403,
                 auth_token=self.mngr_token)
        self.delete(other_url,
                    expected_status=405,
                    auth_token=self.mngr_token)

        # Own job should be GETtable.
        own_job_url = '/api/flamenco/jobs/%s' % self.job_id
        own_job = self.get(own_job_url,
                           expected_status=200,
                           auth_token=self.mngr_token).json()
        resp = self.get('/api/flamenco/jobs',
                        expected_status=200,
                        auth_token=self.mngr_token).json()
        jobs = resp['_items']
        self.assertEqual(1, len(jobs))
        self.assertEqual(1, resp['_meta']['total'])
        self.assertEqual(str(self.job_id), jobs[0]['_id'])

        # Own job should not be modifyable.
        self.put(own_job_url, json=own_job,
                 expected_status=403,
                 auth_token=self.mngr_token)
        self.delete(own_job_url,
                    expected_status=403,
                    auth_token=self.mngr_token)

        # Managers may not create new jobs
        new_job = remove_private_keys(own_job)
        self.post('/api/flamenco/jobs', json=new_job,
                  expected_status=403,
                  auth_token=self.mngr_token)

        # Job of other manager should not be GETtable.
        self.get('/api/flamenco/jobs/%s' % self.job2_id,
                 expected_status=403,
                 auth_token=self.mngr_token)

        # Manager should not have direct access to tasks; only via scheduler.
        self.get('/api/flamenco/tasks',
                 expected_status=403,
                 auth_token=self.mngr_token)
        # Manager should be able to fetch their own tasks, once the IDs are known.
        self.get('/api/flamenco/tasks/%s' % self.tasks_for_job[0]['_id'],
                 expected_status=200,
                 auth_token=self.mngr_token)

    def test_manager_list_as_outside_subscriber(self):
        """Subscriber not member of any Flamenco project should get an empty list of managers."""

        self.create_user(24 * 'e', roles={'subscriber'}, token='subscriber-token')

        resp = self.get('/api/flamenco/managers/',
                        expected_status=200,
                        auth_token='subscriber-token').json()

        self.assertEqual([], resp['_items'])
        self.assertEqual(1, resp['_meta']['page'])
        self.assertEqual(0, resp['_meta']['total'])

    def test_manager_list_as_fladmin(self):
        """Flamenco admin should get complete list of managers."""

        self.create_user(24 * 'f', roles={'flamenco-admin'}, token='fladmin-token')

        resp = self.get('/api/flamenco/managers/',
                        expected_status=200,
                        auth_token='fladmin-token').json()

        expected_manager1 = self.get('/api/flamenco/managers/%s' % self.mngr_id,
                                     expected_status=200,
                                     auth_token=self.mngr_token).json()
        expected_manager2 = self.get('/api/flamenco/managers/%s' % self.mngr2_id,
                                     expected_status=200,
                                     auth_token=self.mngr2_token).json()

        self.assertEqual(2, resp['_meta']['total'])
        self.assertEqual(expected_manager1, resp['_items'][0])
        self.assertEqual(expected_manager2, resp['_items'][1])

    def test_manager_list_as_owner(self):
        self.create_user(24 * 'd',
                         roles={'subscriber'},
                         groups=[self.mngr_doc['owner']],
                         token='owner1-token')
        self.create_user(24 * 'e',
                         roles={'demo'},
                         groups=[self.mngr2_doc['owner']],
                         token='owner2-token')
        resp1 = self.get('/api/flamenco/managers/',
                         expected_status=200,
                         auth_token='owner1-token').json()
        resp2 = self.get('/api/flamenco/managers/',
                         expected_status=200,
                         auth_token='owner2-token').json()
        self.assertEqual(1, resp1['_meta']['total'])
        self.assertEqual(1, resp2['_meta']['total'])
        self.assertEqual(str(self.mngr_id), resp1['_items'][0]['_id'])
        self.assertEqual(str(self.mngr2_id), resp2['_items'][0]['_id'])

    def test_manager_list_as_projmember_subscriber(self):
        """Subscriber member of a Flamenco project should not get a list of managers.

        The user can access specific managers assigned to her projects, but listing
        only returns owned managers.
        """

        self.create_project_member(24 * 'e', roles={'subscriber'}, token='subscriber-token')
        self.assign_manager_to_project(self.mngr_id, self.proj_id)

        resp = self.get('/api/flamenco/managers/',
                        expected_status=200,
                        auth_token='subscriber-token').json()

        self.assertEqual(1, resp['_meta']['page'])
        self.assertEqual(0, resp['_meta']['total'])
        self.assertEqual([], resp['_items'])

        # Project-assigned manager
        self.get('/api/flamenco/managers/%s' % self.mngr_id,
                 expected_status=200,
                 auth_token='subscriber-token')

        # Not project-assigned manager
        self.get('/api/flamenco/managers/%s' % self.mngr2_id,
                 expected_status=403,
                 auth_token='subscriber-token')


class UserAccessTest(AbstractAccessTest):
    def setUp(self, **kwargs):
        super().setUp(**kwargs)

        # Create multiple projects:
        # 1) user is member, both non-owned and owned manager assigned to it.
        # 2) user is member, no manager assigned to it.
        # 3) user is not member, both non-owned and owned manager assigned to it.
        # 4) user is not member, only non-owned manager assigned to it.

        from pillar.api.projects.utils import get_admin_group_id

        # Create the projects
        self.project1 = self._create_user_and_project(user_id=24 * '1',
                                                      roles={'subscriber'},
                                                      project_name='Prøject 1',
                                                      token='token-proj1-owner')
        self.project2 = self._create_user_and_project(user_id=24 * '2',
                                                      roles={'subscriber'},
                                                      project_name='Prøject 2',
                                                      token='token-proj1-owner')
        self.project3 = self._create_user_and_project(user_id=24 * '3',
                                                      roles={'subscriber'},
                                                      project_name='Prøject 3',
                                                      token='token-proj3-owner')
        self.project4 = self._create_user_and_project(user_id=24 * '4',
                                                      roles={'subscriber'},
                                                      project_name='Prøject 4',
                                                      token='token-proj4-owner')
        self.prid1 = bson.ObjectId(self.project1['_id'])
        self.prid2 = bson.ObjectId(self.project2['_id'])
        self.prid3 = bson.ObjectId(self.project3['_id'])
        self.prid4 = bson.ObjectId(self.project4['_id'])

        # Create the managers
        self.owned_mngr, _, self.owned_mngr_token = self.create_manager_service_account()
        self.owned_mngr_id = bson.ObjectId(self.owned_mngr['_id'])
        self.nonowned_mngr, _, self.nonowned_mngr_token = self.create_manager_service_account()
        self.nonowned_mngr_id = bson.ObjectId(self.nonowned_mngr['_id'])

        self.assign_manager_to_project(self.owned_mngr_id, self.prid1)
        self.assign_manager_to_project(self.nonowned_mngr_id, self.prid1)
        self.assign_manager_to_project(self.owned_mngr_id, self.prid3)
        self.assign_manager_to_project(self.nonowned_mngr_id, self.prid3)
        self.assign_manager_to_project(self.nonowned_mngr_id, self.prid4)

        # Create the test user.
        with self.app.test_request_context():
            self.admin_gid1 = get_admin_group_id(self.prid1)
            self.admin_gid2 = get_admin_group_id(self.prid2)
        self.create_user(groups=[
            self.admin_gid1,
            self.admin_gid2,
            self.owned_mngr['owner'],
        ], token='user-token')

    def test_web_current_user_may_use_project(self):
        # Test the user's access to Flamenco on the different projects.

        # 1) user is member, both non-owned and owned manager assigned to it.
        # 2) user is member, no manager assigned to it.
        # 3) user is not member, both non-owned and owned manager assigned to it.
        # 4) user is not member, only non-owned manager assigned to it.

        import pillar.auth

        auth = self.flamenco.auth

        with self.app.test_request_context():
            pillar.auth.login_user('user-token', load_from_db=True)
            self.assertTrue(auth.web_current_user_may_use_project(self.prid1))
            self.assertFalse(auth.web_current_user_may_use_project(self.prid2))
            self.assertFalse(auth.web_current_user_may_use_project(self.prid3))
            self.assertFalse(auth.web_current_user_may_use_project(self.prid4))

    def test_web_current_user_may_use_project_flamenco_admin(self):
        # Flamenco admins have access to all of Flamenco, but only on projects they are part of.
        import pillar.auth

        auth = self.flamenco.auth

        self.create_user(user_id=24 * 'f',
                         roles={'flamenco-admin'},
                         groups=[self.admin_gid1, self.admin_gid2],
                         token='fladmin-token')

        with self.app.test_request_context():
            pillar.auth.login_user('fladmin-token', load_from_db=True)
            self.assertTrue(auth.web_current_user_may_use_project(self.prid1))
            self.assertTrue(auth.web_current_user_may_use_project(self.prid2))
            self.assertFalse(auth.web_current_user_may_use_project(self.prid3))
            self.assertFalse(auth.web_current_user_may_use_project(self.prid4))
