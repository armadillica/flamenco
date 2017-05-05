from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class ManagerAccessTest(AbstractFlamencoTest):
    """Test for access to manager info."""

    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']
        self.mngr_doc = mngr_doc
        self.mngr_token = token['token']

        self.create_user(user_id=24 * 'f', roles={'flamenco-admin'}, token='fladmin-token')

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

    def test_assign_manager_to_project(self):
        """The owner of a manager should be able to assign it to any project she's a member of."""

        self.create_user(24 * 'd',
                         roles={'subscriber'},
                         groups=[self.mngr_doc['owner']],
                         token='owner-token')

        self.create_project_member(user_id=24 * 'e',
                                   roles={'subscriber'},
                                   token='subscriber-token')

        self.patch(
            '/api/flamenco/managers/%s' % self.mngr_id,
            json={'op': 'assign-to-project',
                  'project': self.proj_id},
            auth_token='owner-token',
            expected_status=200,
        )
