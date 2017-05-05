# -*- encoding: utf-8 -*-

from pillar.tests import common_test_data as ctd
from pillar.api.utils.authentication import force_cli_user

from abstract_flamenco_test import AbstractFlamencoTest


class AccessTest(AbstractFlamencoTest):
    """Creates a manager, job and tasks, to check access by different types of users.

    There are also separate access tests in other test cases.
    """

    def _create_project(self, project_name, token):
        resp = self.post('/api/p/create',
                         headers={'Authorization': self.make_header(token)},
                         expected_status=201,
                         data={'project_name': project_name})
        return resp.json()

    def _create_user_and_project(self, roles, user_id='cafef00df00df00df00df00d', token='token',
                                 project_name='Prøject El Niño'):
        self.create_user(user_id, roles, token=token)
        return self._create_project(project_name, token)

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
        """Subscriber member of a Flamenco project should get the list project-specific managers."""

        self.create_project_member(24 * 'e', roles={'subscriber'}, token='subscriber-token')

        resp = self.get('/api/flamenco/managers/',
                        expected_status=200,
                        auth_token='subscriber-token').json()

        expected_manager = self.get('/api/flamenco/managers/%s' % self.mngr_id,
                                    expected_status=200,
                                    auth_token=self.mngr_token).json()

        self.assertEqual(expected_manager, resp['_items'][0])
        self.assertEqual(1, resp['_meta']['page'])
        self.assertEqual(1, resp['_meta']['total'])
