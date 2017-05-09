import bson

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

        self.create_project_member(user_id=24 * 'd',
                                   roles={'subscriber'},
                                   groups=[self.mngr_doc['owner']],
                                   token='owner-projmember-token')

        # User who is both owner and project member can assign.
        self.patch(
            f'/api/flamenco/managers/{self.mngr_id}',
            json={'op': 'assign-to-project',
                  'project': self.proj_id},
            auth_token='owner-projmember-token',
            expected_status=204,
        )
        self.assertManagerIsAssignedToProject(self.mngr_id, self.proj_id)

        self.patch(
            f'/api/flamenco/managers/{self.mngr_id}',
            json={'op': 'remove-from-project',
                  'project': self.proj_id},
            auth_token='owner-projmember-token',
            expected_status=204,
        )

        self.assertManagerIsNotAssignedToProject(self.mngr_id, self.proj_id)

    def test_assign_manager_to_project_denied(self):
        """Non-project members and non-owners should not be able to assign."""

        self.create_user(24 * 'c',
                         roles={'subscriber'},
                         groups=[self.mngr_doc['owner']],
                         token='owner-nonprojmember-token')

        self.create_project_member(user_id=24 * 'e',
                                   roles={'subscriber'},
                                   token='projmember-token')

        # Owner-only user cannot assign to project.
        self.patch(
            f'/api/flamenco/managers/{self.mngr_id}',
            json={'op': 'assign-to-project',
                  'project': self.proj_id},
            auth_token='owner-nonprojmember-token',
            expected_status=403,
        )

        # User who is project member but not owner the Manager cannot assign.
        self.patch(
            f'/api/flamenco/managers/{self.mngr_id}',
            json={'op': 'assign-to-project',
                  'project': self.proj_id},
            auth_token='projmember-token',
            expected_status=403,
        )

        self.assertManagerIsNotAssignedToProject(self.mngr_id, self.proj_id)

    def assertManagerIsAssignedToProject(self, mngr_id: bson.ObjectId, proj_id: bson.ObjectId):
        projects = self._get_mngr_projects(mngr_id)
        if not projects:
            self.fail(f'Manager {mngr_id} is not assigned to any project')

        if proj_id not in projects:
            projs = ', '.join(f"'{pid}'" for pid in projects)
            self.fail(f'Manager {mngr_id} is not assigned to project {proj_id}, only to {projs}')

    def assertManagerIsNotAssignedToProject(self, mngr_id: bson.ObjectId, proj_id: bson.ObjectId):
        projects = self._get_mngr_projects(mngr_id)

        if proj_id not in projects:
            return

        if len(projects) > 1:
            projs = ', '.join(f"'{pid}'" for pid in projects
                              if pid != proj_id)
            self.fail(f'Manager {mngr_id} unexpectedly assigned to project {proj_id} '
                      f'(as well as {projs})')
        else:
            self.fail(f'Manager {mngr_id} unexpectedly assigned to project {proj_id}')

    def _get_mngr_projects(self, mngr_id: bson.ObjectId) -> list:
        from flamenco import current_flamenco

        with self.app.test_request_context():
            mngr_coll = current_flamenco.db('managers')
            mngr = mngr_coll.find_one(mngr_id)

        return mngr.get('projects', [])
