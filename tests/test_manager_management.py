import datetime

import bson
from bson.tz_util import utc

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class ManagerAccessTest(AbstractFlamencoTest):
    """Test for access to manager info."""

    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        from pillar.api.utils.authentication import force_cli_user

        self.create_manager()
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

        self.create_project_member(user_id=24 * 'd',
                                   roles=set(),
                                   groups=[self.mngr_doc['owner']],
                                   token='nonfluser-token')

        # Owner-only user cannot assign to project.
        self.patch(
            f'/api/flamenco/managers/{self.mngr_id}',
            json={'op': 'assign-to-project',
                  'project': self.proj_id},
            auth_token='owner-nonprojmember-token',
            expected_status=403,
        )

        # User who is project member but not owner of the Manager cannot assign.
        self.patch(
            f'/api/flamenco/managers/{self.mngr_id}',
            json={'op': 'assign-to-project',
                  'project': self.proj_id},
            auth_token='projmember-token',
            expected_status=403,
        )

        # Owner who is project member but not subscriber cannot assign.
        self.patch(
            f'/api/flamenco/managers/{self.mngr_id}',
            json={'op': 'assign-to-project',
                  'project': self.proj_id},
            auth_token='nonfluser-token',
            expected_status=403,
        )

        self.assertManagerIsNotAssignedToProject(self.mngr_id, self.proj_id)

    def assertManagerIsAssignedToProject(self,
                                         manager_id: bson.ObjectId,
                                         project_id: bson.ObjectId):
        manager = self._get_manager_from_db(manager_id)
        projects = manager.get('projects', [])

        if not projects:
            self.fail(f'Manager {manager_id} is not assigned to any project')

        if project_id not in projects:
            projs = ', '.join(f"'{pid}'" for pid in projects)
            self.fail(
                f'Manager {manager_id} is not assigned to project {project_id}, only to {projs}')

        # Check that the admin group of the project is contained in the manager's group.
        with self.app.test_request_context():
            proj_coll = self.app.db().projects
            project = proj_coll.find_one({'_id': project_id}, {'permissions': 1})

        if not project:
            self.fail(f'Project {project_id} does not exist.')

        admin_group_id = project['permissions']['groups'][0]['group']
        user_groups = manager.get('user_groups', [])
        if admin_group_id not in user_groups:
            self.fail(f"Admin group {admin_group_id} is not contained in "
                      f"{manager_id}'s user_groups {user_groups}")

    def assertManagerIsNotAssignedToProject(self,
                                            manager_id: bson.ObjectId,
                                            project_id: bson.ObjectId):
        manager = self._get_manager_from_db(manager_id)
        projects = manager.get('projects', [])

        if project_id in projects:
            if len(projects) > 1:
                projs = ', '.join(f"'{pid}'" for pid in projects
                                  if pid != project_id)
                self.fail(f'Manager {manager_id} unexpectedly assigned to project {project_id} '
                          f'(as well as {projs})')
            else:
                self.fail(f'Manager {manager_id} unexpectedly assigned to project {project_id}')

        # Check that the admin group of the project is not contained in the manager's group.
        with self.app.test_request_context():
            proj_coll = self.app.db().projects
            project = proj_coll.find_one({'_id': project_id}, {'permissions': 1})

        if not project:
            self.fail(f'Project {project_id} does not exist.')

        admin_group_id = project['permissions']['groups'][0]['group']
        user_groups = manager.get('user_groups', [])
        if admin_group_id in user_groups:
            self.fail(f"Admin group {admin_group_id} is contained in "
                      f"{manager_id}'s user_groups {user_groups}")

    def _get_manager_from_db(self, mngr_id: bson.ObjectId) -> dict:
        from flamenco import current_flamenco

        with self.app.test_request_context():
            mngr_coll = current_flamenco.db('managers')
            return mngr_coll.find_one(mngr_id)

    def test_gen_new_auth_token(self):
        from pillar.api import service

        with self.app.test_request_context():
            tokens_coll = self.app.db('tokens')
            service_account_id = self.flamenco.manager_manager.find_service_account_id(self.mngr_id)

            # Create a new more tokens
            service.generate_auth_token(service_account_id)
            service.generate_auth_token(service_account_id)
            service.generate_auth_token(service_account_id)

            all_tokens = tokens_coll.find({'user': service_account_id})
            self.assertEqual(all_tokens.count(), 4)

            token = self.flamenco.manager_manager.gen_new_auth_token(self.mngr_id)

            # There can be only one, rest should have been deleted.
            all_tokens = tokens_coll.find({'user': service_account_id})
            self.assertEqual(all_tokens.count(), 1)

        self.assertNotEqual(token.token, self.mngr_token)
        self.assertTrue(token.token.startswith('SRV'))
        self.assertTrue(token.expire_time > datetime.datetime.now(tz=utc))

    def test_revoke_auth_token(self):
        from pillar.api import service

        with self.app.test_request_context():
            tokens_coll = self.app.db('tokens')
            service_account_id = self.flamenco.manager_manager.find_service_account_id(self.mngr_id)

            # Create a new more tokens
            service.generate_auth_token(service_account_id)
            service.generate_auth_token(service_account_id)
            service.generate_auth_token(service_account_id)

            all_tokens = tokens_coll.find({'user': service_account_id})
            self.assertEqual(all_tokens.count(), 4)

            self.flamenco.manager_manager.revoke_auth_token(self.mngr_id)

            # All should have been deleted.
            all_tokens = tokens_coll.find({'user': service_account_id})
            self.assertEqual(all_tokens.count(), 0)

    def test_share(self):

        owner_gid = self.mngr_doc['owner']
        self.create_user(24 * 'a', roles={'subscriber'}, groups=[owner_gid],
                         token='owner-token')
        subject_uid = 24 * 'b'
        self.create_user(subject_uid, roles={'subscriber'},
                         token='subject-token')

        self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                   json={
                       'op': 'change-ownership',
                       'action': 'share',
                       'user': subject_uid,
                   },
                   auth_token='owner-token',
                   expected_status=204)

        user = self.get('/api/users/me', auth_token='subject-token').json
        self.assertIn(str(owner_gid), user['groups'])

    def test_unshare(self):
        owner_gid = self.mngr_doc['owner']
        self.create_user(24 * 'a', roles={'subscriber'}, groups=[owner_gid],
                         token='owner-token')
        self.create_user(24 * 'b', roles={'subscriber'}, groups=[owner_gid],
                         token='subject-token')

        self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                   json={
                       'op': 'change-ownership',
                       'action': 'unshare',
                       'user': 24 * 'b',
                   },
                   auth_token='owner-token',
                   expected_status=204)

        user = self.get('/api/users/me', auth_token='subject-token').json
        self.assertNotIn(str(owner_gid), user['groups'])

    def test_share_with_non_flamenco_subject(self):
        owner_gid = self.mngr_doc['owner']
        self.create_user(24 * 'a', roles={'subscriber'}, groups=[owner_gid],
                         token='owner-token')
        subject_uid = 24 * 'b'
        self.create_user(subject_uid, roles=set(),
                         token='subject-token')

        self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                   json={
                       'op': 'change-ownership',
                       'action': 'share',
                       'user': subject_uid,
                   },
                   auth_token='owner-token',
                   expected_status=403)

        user = self.get('/api/users/me', auth_token='subject-token').json
        self.assertNotIn(str(owner_gid), user['groups'])

    def test_share_with_non_flamenco_user(self):
        owner_gid = self.mngr_doc['owner']
        self.create_user(24 * 'a', roles={'subscriber'}, groups=[owner_gid],
                         token='owner-token')
        subject_uid = 24 * 'b'
        self.create_user(subject_uid, roles=set(),
                         token='subject-token')

        self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                   json={
                       'op': 'change-ownership',
                       'action': 'share',
                       'user': subject_uid,
                   },
                   auth_token='owner-token',
                   expected_status=403)

        user = self.get('/api/users/me', auth_token='subject-token').json
        self.assertNotIn(str(owner_gid), user['groups'])

    def test_hand_over_manager(self):
        owner_gid = self.mngr_doc['owner']
        self.create_user(24 * 'a', roles={'subscriber'}, groups=[owner_gid],
                         token='owner-token')
        subject_uid = 24 * 'b'
        self.create_user(subject_uid, roles={'subscriber'},
                         token='subject-token')

        # Share with subject-user
        self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                   json={
                       'op': 'change-ownership',
                       'action': 'share',
                       'user': subject_uid,
                   },
                   auth_token='owner-token',
                   expected_status=204)

        # Unshare by subject-user
        self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                   json={
                       'op': 'change-ownership',
                       'action': 'unshare',
                       'user': 24 * 'a',
                   },
                   auth_token='subject-token',
                   expected_status=204)

        old_owner = self.get('/api/users/me', auth_token='owner-token').json
        new_owner = self.get('/api/users/me', auth_token='subject-token').json

        self.assertNotIn(str(owner_gid), old_owner['groups'])
        self.assertIn(str(owner_gid), new_owner['groups'])

    def test_hand_over_manager_abandon(self):
        owner_gid = self.mngr_doc['owner']
        self.create_user(24 * 'a', roles={'subscriber'}, groups=[owner_gid],
                         token='owner-token')
        subject_uid = 24 * 'b'
        self.create_user(subject_uid, roles={'subscriber'},
                         token='subject-token')

        # Share with subject-user by owner
        self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                   json={
                       'op': 'change-ownership',
                       'action': 'share',
                       'user': subject_uid,
                   },
                   auth_token='owner-token',
                   expected_status=204)

        # Abandon by owner
        self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                   json={
                       'op': 'change-ownership',
                       'action': 'unshare',
                       'user': 24 * 'a',
                   },
                   auth_token='owner-token',
                   expected_status=204)

        old_owner = self.get('/api/users/me', auth_token='owner-token').json
        new_owner = self.get('/api/users/me', auth_token='subject-token').json

        self.assertNotIn(str(owner_gid), old_owner['groups'])
        self.assertIn(str(owner_gid), new_owner['groups'])

    def test_unshare_self(self):
        owner_gid = self.mngr_doc['owner']
        owner_uid = 24 * 'a'
        self.create_user(owner_uid, roles={'subscriber'}, groups=[owner_gid],
                         token='owner-token')
        subject_uid = 24 * 'b'
        self.create_user(subject_uid, roles={'subscriber'}, groups=[owner_gid],
                         token='other-token')

        self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                   json={
                       'op': 'change-ownership',
                       'action': 'unshare',
                       'user': owner_uid,
                   },
                   auth_token='owner-token',
                   expected_status=204)

        user = self.get('/api/users/me', auth_token='owner-token').json
        self.assertNotIn(str(owner_gid), user['groups'])

    def test_unshare_last_user(self):
        owner_gid = self.mngr_doc['owner']
        owner_uid = 24 * 'a'
        self.create_user(owner_uid, roles={'subscriber'}, groups=[owner_gid],
                         token='owner-token')
        other_uid = 24 * 'b'
        self.create_user(other_uid, roles={'subscriber'}, groups=[owner_gid],
                         token='other-token')

        for uid in (self.mngr_owner, other_uid):
            self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                       json={
                           'op': 'change-ownership',
                           'action': 'unshare',
                           'user': uid,
                       },
                       auth_token='owner-token',
                       expected_status=204)

        self.patch(f'/api/flamenco/managers/{self.mngr_id}',
                   json={
                       'op': 'change-ownership',
                       'action': 'unshare',
                       'user': owner_uid,
                   },
                   auth_token='owner-token',
                   expected_status=400)

        user = self.get('/api/users/me', auth_token='owner-token').json
        self.assertIn(str(owner_gid), user['groups'])

    def test_owning_users(self):
        owner_gid = self.mngr_doc['owner']
        self.create_user(24 * 'a', roles={'subscriber'}, groups=[owner_gid])
        self.create_user(24 * 'b', roles={'subscriber'})
        self.create_user(24 * 'c', roles=[], groups=[owner_gid])

        with self.app.test_request_context():
            owners = self.flamenco.manager_manager.owning_users(owner_gid)

        owner_ids = {o['_id'] for o in owners}

        self.assertEqual(
            owner_ids, {self.mngr_owner, bson.ObjectId(24 * 'a'), bson.ObjectId(24 * 'c')})

        # Try with a non existing group
        faux_owner_gid = bson.ObjectId()

        with self.app.test_request_context():
            owners = self.flamenco.manager_manager.owning_users(faux_owner_gid)

        owner_ids = {o['_id'] for o in owners}
        self.assertEqual(owner_ids, set())
