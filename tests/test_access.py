# -*- encoding: utf-8 -*-

from pillar.tests import common_test_data as ctd
from pillar.api.utils.authentication import force_cli_user

from abstract_flamenco_test import AbstractFlamencoTest


class AccessTest(AbstractFlamencoTest):
    """Creates a manager, job and tasks, to check access by different types of users."""

    def _create_user_with_token(self, roles, token, user_id='cafef00df00df00df00df00d'):
        user_id = self.create_user(roles=roles, user_id=user_id)
        self.create_valid_auth_token(user_id, token)
        return user_id

    def _create_project(self, project_name, token):
        resp = self.post('/api/p/create',
                         headers={'Authorization': self.make_header(token)},
                         expected_status=201,
                         data={'project_name': project_name})
        return resp.json()

    def _create_user_and_project(self, roles, user_id='cafef00df00df00df00df00d', token='token',
                                 project_name='Prøject El Niño'):
        self._create_user_with_token(roles, token, user_id=user_id)
        return self._create_project(project_name, token)

    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from flamenco import current_flamenco

        # Main project will have a manager, job, and tasks.
        mngr_doc, _, token = self.create_manager_service_account()

        self.mngr_id = mngr_doc['_id']
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
                 expected_status=403,
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
