# -*- encoding: utf-8 -*-
import typing

import bson

from pillar.tests import common_test_data as ctd

from abstract_flamenco_test import AbstractFlamencoTest


class AbstractAccessTest(AbstractFlamencoTest):
    def _create_project(self, project_name, token) -> dict:
        resp = self.post('/api/p/create',
                         headers={'Authorization': self.make_header(token)},
                         expected_status=201,
                         data={'project_name': project_name,
                               'is_private': True})
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
        from pillar.api.utils.authentication import force_cli_user

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
            owner_email='manager2@example.com', name='manager 2'
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
                 etag=own_doc['_etag'],
                 expected_status=403,
                 auth_token=self.mngr_token)
        self.delete(own_url,
                    expected_status=405,
                    etag=own_doc['_etag'],
                    auth_token=self.mngr_token)
        self.put(other_url, json=remove_private_keys(own_doc),
                 expected_status=403,
                 etag=self.mngr2_doc['_etag'],
                 auth_token=self.mngr_token)
        self.delete(other_url,
                    expected_status=405,
                    etag=self.mngr2_doc['_etag'],
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
        self.put(own_job_url, json=remove_private_keys(own_job),
                 etag=own_job['_etag'],
                 expected_status=403,
                 auth_token=self.mngr_token)
        self.delete(own_job_url,
                    etag=own_job['_etag'],
                    expected_status=403,
                    auth_token=self.mngr_token)
        self.delete('/api/flamenco/jobs',
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

    def test_manager_list_as_nonfluser_owner(self):
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

    def test_manager_list_as_nonprojmember_subscriber(self):
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

    def test_manager_as_subscriber(self):
        """Subscriber/Flamenco-user member of a Flamenco project should not get a list of managers.

        The user can access specific managers assigned to her projects, but listing
        only returns owned managers.
        """

        self.create_project_member(24 * 'e',
                                   roles={'subscriber'},
                                   token='flamuser-token')
        self.assign_manager_to_project(self.mngr_id, self.proj_id)

        resp = self.get('/api/flamenco/managers/',
                        expected_status=200,
                        auth_token='flamuser-token').json()

        self.assertEqual(1, resp['_meta']['page'])
        self.assertEqual(0, resp['_meta']['total'])
        self.assertEqual([], resp['_items'])

        # Project-assigned manager
        self.get('/api/flamenco/managers/%s' % self.mngr_id,
                 expected_status=200,
                 auth_token='flamuser-token')

        # Not project-assigned manager
        self.get('/api/flamenco/managers/%s' % self.mngr2_id,
                 expected_status=403,
                 auth_token='flamuser-token')


class UserAccessTest(AbstractAccessTest):
    def setUp(self, **kwargs):
        super().setUp(**kwargs)

        # Create multiple projects:
        # 1) user is member, owned manager assigned to it.
        # 2) user is member, non-owned manager assigned to it.
        # 3) user is member, no manager assigned to it.
        # 4) user is not member, both non-owned and owned manager assigned to it.
        # 5) user is not member, only non-owned manager assigned to it.
        # 6) user is GET-only member, owned manager assigned to it.
        # 7) user is GET-only member, non-owned manager assigned to it.

        from pillar.api.projects.utils import get_admin_group_id
        from pillar.api.utils import remove_private_keys

        # Create the projects
        self.project: typing.MutableMapping[int, dict] = {}
        self.prid: typing.MutableMapping[int, bson.ObjectId] = {}

        for idx in range(1, 8):
            admin_id = 24 * str(idx)
            proj = self._create_user_and_project(user_id=admin_id,
                                                 roles={'subscriber'},
                                                 project_name=f'Prøject {idx}',
                                                 token=f'token-proj{idx}-admin')
            self.project[idx] = proj
            self.prid[idx] = bson.ObjectId(proj['_id'])

        # For projects 6 and 7, add GET access group
        self.group_map = self.create_standard_groups(additional_groups=['get-only-6', 'get-only-7'])
        for idx in (6, 7):
            self.project[idx]['permissions']['groups'].append({
                'group': self.group_map[f'get-only-{idx}'],
                'methods': ['GET'],
            })
            self.put(f'/api/projects/{self.prid[idx]}',
                     json=remove_private_keys(self.project[idx]),
                     etag=self.project[idx]['_etag'],
                     auth_token=f'token-proj{idx}-admin')

        # Create the managers
        self.owned_mngr, _, self.owned_mngr_token = self.create_manager_service_account()
        self.owned_mngr_id = bson.ObjectId(self.owned_mngr['_id'])
        self.nonowned_mngr, _, self.nonowned_mngr_token = self.create_manager_service_account()
        self.nonowned_mngr_id = bson.ObjectId(self.nonowned_mngr['_id'])

        self.assign_manager_to_project(self.owned_mngr_id, self.prid[1])
        self.assign_manager_to_project(self.nonowned_mngr_id, self.prid[2])
        self.assign_manager_to_project(self.owned_mngr_id, self.prid[4])
        self.assign_manager_to_project(self.nonowned_mngr_id, self.prid[5])
        self.assign_manager_to_project(self.owned_mngr_id, self.prid[6])
        self.assign_manager_to_project(self.nonowned_mngr_id, self.prid[7])

        # Create the test user.
        self.admin_gid: typing.MutableMapping[int, bson.ObjectId] = {}
        with self.app.test_request_context():
            for idx, prid in self.prid.items():
                self.admin_gid[idx] = get_admin_group_id(prid)
        self.create_user(
            roles={'subscriber'},
            groups=[
                self.admin_gid[1],
                self.admin_gid[2],
                self.admin_gid[3],
                self.owned_mngr['owner'],
                self.group_map['get-only-6'],
                self.group_map['get-only-7'],
            ], token='user-token')

        # Make some assertions about the access rights on the projects.
        for idx in (1, 2, 3):
            p = self.get(f'/api/projects/{self.prid[idx]}', auth_token='user-token').json()
            self.assertEqual({'GET', 'PUT', 'DELETE', 'POST'}, set(p['allowed_methods']),
                             f'Unexpected methods {p["allowed_methods"]} in project nr {idx}')
        for idx in (4, 5):
            self.get(f'/api/projects/{self.prid[idx]}', auth_token='user-token',
                     expected_status=403)
        for idx in (6, 7):
            p = self.get(f'/api/projects/{self.prid[idx]}', auth_token='user-token').json()
            self.assertEqual({'GET'}, set(p['allowed_methods']),
                             f'Unexpected methods {p["allowed_methods"]} in project nr {idx}')

    def test_current_user_may_use_project(self):
        # Test the user's access to Flamenco on the different projects.

        # 1) user is member, owned manager assigned to it.
        # 2) user is member, non-owned manager assigned to it.
        # 3) user is member, no manager assigned to it.
        # 4) user is not member, both non-owned and owned manager assigned to it.
        # 5) user is not member, only non-owned manager assigned to it.
        # 6) user is GET-only member, owned manager assigned to it.
        # 7) user is GET-only member, non-owned manager assigned to it.

        import pillar.auth

        auth = self.flamenco.auth

        with self.app.test_request_context():
            pillar.auth.login_user('user-token', load_from_db=True)
            self.assertTrue(auth.current_user_may(auth.Actions.USE, self.prid[1]))
            self.assertTrue(auth.current_user_may(auth.Actions.USE, self.prid[2]))
            self.assertFalse(auth.current_user_may(auth.Actions.USE, self.prid[3]))
            self.assertFalse(auth.current_user_may(auth.Actions.USE, self.prid[4]))
            self.assertFalse(auth.current_user_may(auth.Actions.USE, self.prid[5]))
            self.assertFalse(auth.current_user_may(auth.Actions.USE, self.prid[6]))
            self.assertFalse(auth.current_user_may(auth.Actions.USE, self.prid[7]))

    def test_current_user_may_use_project_flamenco_admin(self):
        # Flamenco admins have access to all of Flamenco, but only on projects they are part of.
        import pillar.auth

        auth = self.flamenco.auth

        self.create_user(user_id=24 * 'f',
                         roles={'flamenco-admin'},
                         groups=[self.admin_gid[1], self.admin_gid[2], self.admin_gid[3]],
                         token='fladmin-token')

        with self.app.test_request_context():
            pillar.auth.login_user('fladmin-token', load_from_db=True)
            self.assertTrue(auth.current_user_may(auth.Actions.USE, self.prid[1]))
            self.assertTrue(auth.current_user_may(auth.Actions.USE, self.prid[2]))
            self.assertTrue(auth.current_user_may(auth.Actions.USE, self.prid[3]))
            self.assertFalse(auth.current_user_may(auth.Actions.USE, self.prid[4]))
            self.assertFalse(auth.current_user_may(auth.Actions.USE, self.prid[5]))
            self.assertFalse(auth.current_user_may(auth.Actions.USE, self.prid[6]))
            self.assertFalse(auth.current_user_may(auth.Actions.USE, self.prid[7]))
