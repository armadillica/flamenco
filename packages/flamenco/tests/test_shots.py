# -*- encoding: utf-8 -*-

import unittest

import responses
from bson import ObjectId

import pillarsdk
import pillarsdk.exceptions as sdk_exceptions
import pillar.tests
import pillar.auth
import pillar.tests.common_test_data as ctd

from abstract_flamenco_test import AbstractFlamencoTest


class AbstractShotTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        self.tmngr = self.app.pillar_extensions['flamenco'].task_manager
        self.smngr = self.app.pillar_extensions['flamenco'].shot_manager

        self.proj_id, self.project = self.ensure_project_exists()

        self.sdk_project = pillarsdk.Project(pillar.tests.mongo_to_sdk(self.project))

    def create_task(self, shot_id, task_type):
        with self.app.test_request_context():
            # Log in as project admin user
            pillar.auth.login_user(ctd.EXAMPLE_PROJECT_OWNER_ID)

            self.mock_blenderid_validate_happy()
            task = self.tmngr.create_task(self.sdk_project, parent=shot_id, task_type=task_type)

        self.assertIsInstance(task, pillarsdk.Node)
        return task

    def create_shot(self):
        with self.app.test_request_context():
            # Log in as project admin user
            pillar.auth.login_user(ctd.EXAMPLE_PROJECT_OWNER_ID)

            self.mock_blenderid_validate_happy()
            shot = self.smngr.create_shot(self.sdk_project)

        self.assertIsInstance(shot, pillarsdk.Node)
        return shot


class ShotManagerTest(AbstractShotTest):
    @responses.activate
    def test_tasks_for_shot(self):
        shot1 = self.create_shot()
        shot2 = self.create_shot()

        shot1_id = shot1['_id']
        shot2_id = shot2['_id']

        task1 = self.create_task(shot1_id, u'fx')
        task2 = self.create_task(shot1_id, u'fx')
        task3 = self.create_task(shot1_id, u'høken')

        task4 = self.create_task(shot2_id, u'eﬀects')
        task5 = self.create_task(shot2_id, u'eﬀects')
        task6 = self.create_task(shot2_id, u'ïnžane')

        with self.app.test_request_context():
            # Log in as project admin user
            pillar.auth.login_user(ctd.EXAMPLE_PROJECT_OWNER_ID)

            self.mock_blenderid_validate_happy()
            shot_id_to_task = self.smngr.tasks_for_shots([shot1, shot2],
                                                         [u'fx', u'høken', u'eﬀects'])

        # Just test based on task IDs, as strings are turned into datetimes etc. by the API,
        # so we can't test equality.
        for all_tasks in shot_id_to_task.values():
            for task_type, tasks in all_tasks.items():
                all_tasks[task_type] = {task['_id'] for task in tasks}

        self.assertEqual({
            u'fx': {task1['_id'], task2['_id']},
            u'høken': {task3['_id']},
        }, shot_id_to_task[shot1_id])

        self.assertEqual({
            u'eﬀects': {task4['_id'], task5['_id']},
            None: {task6['_id']},
        }, shot_id_to_task[shot2_id])

    @responses.activate
    def test_edit_shot(self):
        shot = self.create_shot()
        pre_edit_shot = shot.to_dict()

        with self.app.test_request_context():
            # Log in as project admin user
            pillar.auth.login_user(ctd.EXAMPLE_PROJECT_OWNER_ID)

            self.mock_blenderid_validate_happy()

            # No Etag checking, see T49555
            # self.assertRaises(sdk_exceptions.PreconditionFailed,
            #                   self.smngr.edit_shot,
            #                   shot_id=shot['_id'],
            #                   name=u'ผัดไทย',
            #                   description=u'Shoot the Pad Thai',
            #                   status='todo',
            #                   _etag='jemoeder')

            self.smngr.edit_shot(shot_id=shot['_id'],
                                 name=u'ผัดไทย',
                                 description=u'Shoot the Pad Thai',
                                 status='todo',
                                 notes=None,
                                 _etag=shot._etag)

        # Test directly with MongoDB
        with self.app.test_request_context():
            nodes_coll = self.app.data.driver.db['nodes']
            found = nodes_coll.find_one(ObjectId(shot['_id']))
            self.assertEqual(pre_edit_shot['name'], found['name'])  # shouldn't be edited.
            self.assertEqual(u'todo', found['properties']['status'])
            self.assertEqual(u'Shoot the Pad Thai', found['description'])
            self.assertNotIn(u'notes', found['properties'])

    @responses.activate
    def test_shot_summary(self):
        shot1 = self.create_shot()
        shot2 = self.create_shot()
        shot3 = self.create_shot()
        shot4 = self.create_shot()

        with self.app.test_request_context():
            # Log in as project admin user
            pillar.auth.login_user(ctd.EXAMPLE_PROJECT_OWNER_ID)

            self.mock_blenderid_validate_happy()
            for shot, status in zip([shot1, shot2, shot3, shot4],
                                    ['todo', 'in_progress', 'todo', 'final']):
                self.smngr.edit_shot(shot_id=shot['_id'],
                                     status=status,
                                     _etag=shot._etag)

                # def shot_status_summary(self, project_id):


class NodeSetattrTest(unittest.TestCase):
    def test_simple(self):
        from flamenco.shots import node_setattr

        node = {}
        node_setattr(node, 'a', 5)
        self.assertEqual({'a': 5}, node)

        node_setattr(node, 'b', {'complexer': 'value'})
        self.assertEqual({'a': 5, 'b': {'complexer': 'value'}}, node)

    def test_dotted(self):
        from flamenco.shots import node_setattr

        node = {}
        self.assertRaises(KeyError, node_setattr, node, 'a.b', 5)

        node = {'b': {}}
        node_setattr(node, 'b.simple', 'value')
        self.assertEqual({'b': {'simple': 'value'}}, node)

        node_setattr(node, 'b.complex', {'yes': 'value'})
        self.assertEqual({'b': {'simple': 'value',
                                'complex': {'yes': 'value'}}}, node)

        node_setattr(node, 'b.complex', {'yes': 5})
        self.assertEqual({'b': {'simple': 'value',
                                'complex': {'yes': 5}}}, node)

    def test_none_simple(self):
        from flamenco.shots import node_setattr

        node = {}
        node_setattr(node, 'a', None)
        node_setattr(node, None, 'b')
        self.assertEqual({None: 'b'}, node)

    def test_none_dotted(self):
        from flamenco.shots import node_setattr

        node = {}
        self.assertRaises(KeyError, node_setattr, node, 'a.b', None)

        node = {'b': {}}
        node_setattr(node, 'b.simple', None)
        self.assertEqual({'b': {}}, node)

        node_setattr(node, 'b.complex', {'yes': None})
        self.assertEqual({'b': {'complex': {'yes': None}}}, node)

        node_setattr(node, 'b.complex.yes', None)
        self.assertEqual({'b': {'complex': {}}}, node)

        node_setattr(node, 'b.complex', {None: 5})
        self.assertEqual({'b': {'complex': {None: 5}}}, node)


class PatchShotTest(AbstractShotTest):
    @responses.activate
    def test_patch_from_blender_happy(self):
        shot = self.create_shot()
        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')

        url = '/api/nodes/%s' % shot._id
        patch = {
            'op': 'from-blender',
            '$set': {
                'name': u'"shot" is "geschoten" in Dutch',
                'properties.trim_start_in_frames': 123,
                'properties.duration_in_edit_in_frames': 4215,
                'properties.cut_in_timeline_in_frames': 1245,
                'properties.status': u'on_hold',
            }
        }
        self.patch(url, json=patch, auth_token='token')

        dbnode = self.get(url, auth_token='token').json()
        self.assertEqual(u'"shot" is "geschoten" in Dutch', dbnode['name'])
        self.assertEqual(123, dbnode['properties']['trim_start_in_frames'])
        self.assertEqual(u'on_hold', dbnode['properties']['status'])

    @responses.activate
    def test_patch_from_web_happy(self):
        shot = self.create_shot()
        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')

        url = '/api/nodes/%s' % shot._id
        patch = {
            'op': 'from-web',
            '$set': {
                'description': u'Таким образом, этот человек заходит в бар, и говорит…',
                'properties.notes': u'Два бокала вашей лучшей водки, пожалуйста.',
                'properties.status': u'final',
            }
        }
        self.patch(url, json=patch, auth_token='token')

        dbnode = self.get(url, auth_token='token').json()
        self.assertEqual(u'Таким образом, этот человек заходит в бар, и говорит…',
                         dbnode['description'])
        self.assertEqual(u'Два бокала вашей лучшей водки, пожалуйста.',
                         dbnode['properties']['notes'])
        self.assertEqual(u'final', dbnode['properties']['status'])
        self.assertEqual(u'New shot', dbnode['name'])

    @responses.activate
    def test_patch_from_web_happy_nones(self):
        shot = self.create_shot()
        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')

        url = '/api/nodes/%s' % shot._id
        patch = {
            'op': 'from-web',
            '$set': {
                'description': None,
                'properties.notes': None,
                'properties.status': u'final',
            }
        }
        self.patch(url, json=patch, auth_token='token')

        dbnode = self.get(url, auth_token='token').json()
        self.assertNotIn('description', dbnode)
        self.assertNotIn('notes', dbnode['properties'])
        self.assertEqual(u'final', dbnode['properties']['status'])
        self.assertEqual(u'New shot', dbnode['name'])

    @responses.activate
    def test_patch_bad_op(self):
        shot = self.create_shot()
        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')

        url = '/api/nodes/%s' % shot._id
        patch = {'properties.status': 'todo'}
        self.patch(url, json=patch, auth_token='token', expected_status=400)

    @responses.activate
    def test_patch_from_blender_bad_fields(self):
        shot = self.create_shot()
        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')

        url = '/api/nodes/%s' % shot._id
        patch = {
            'op': 'from-blender',
            '$set': {
                'invalid.property': 'JE MOEDER',
            }
        }
        self.patch(url, json=patch, auth_token='token', expected_status=400)

    @responses.activate
    def test_patch_from_blender_bad_status(self):
        shot = self.create_shot()
        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')

        url = '/api/nodes/%s' % shot._id
        patch = {
            'op': 'from-blender',
            '$set': {
                'properties.status': 'JE MOEDER',
            }
        }
        self.patch(url, json=patch, auth_token='token', expected_status=422)

    @responses.activate
    def test_patch_unauthenticated(self):
        shot = self.create_shot()

        url = '/api/nodes/%s' % shot._id
        patch = {
            'op': 'from-blender',
            '$set': {
                'properties.status': 'in_progress',
            }
        }
        self.patch(url, json=patch, expected_status=403)

    @responses.activate
    def test_patch_bad_user(self):
        shot = self.create_shot()

        self.create_user(24 * 'a')
        self.create_valid_auth_token(24 * 'a', 'other')

        url = '/api/nodes/%s' % shot._id
        patch = {
            'op': 'from-blender',
            '$set': {
                'properties.status': 'in_progress',
            }
        }
        self.patch(url, json=patch, auth_token='other', expected_status=403)

    @responses.activate
    def test_patch_unlink(self):
        shot = self.create_shot()
        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')

        url = '/api/nodes/%s' % shot._id

        dbnode = self.get(url, auth_token='token').json()
        self.assertTrue(dbnode['properties']['used_in_edit'])

        patch = {'op': 'unlink'}
        self.patch(url, json=patch, auth_token='token')

        dbnode = self.get(url, auth_token='token').json()
        self.assertFalse(dbnode['properties']['used_in_edit'])

    @responses.activate
    def test_patch_unlink_deleted(self):
        """Unlinking a deleted shot shouldn't undelete it.

        We implement PATCH by changing then PUTing, which undeletes by default.
        """

        shot = self.create_shot()
        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')

        url = '/api/nodes/%s' % shot._id

        # Delete (and verify deletion)
        self.delete(url, auth_token='token',
                    headers={'If-Match': shot['_etag']},
                    expected_status=204)
        self.get(url, auth_token='token', expected_status=404)

        patch = {'op': 'unlink'}
        self.patch(url, json=patch, auth_token='token')
        self.get(url, auth_token='token', expected_status=404)

    @responses.activate
    def test_patch_relink(self):
        shot = self.create_shot()
        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')

        url = '/api/nodes/%s' % shot._id
        self.patch(url, json={'op': 'unlink'}, auth_token='token')

        dbnode = self.get(url, auth_token='token').json()
        self.assertFalse(dbnode['properties']['used_in_edit'])

        self.patch(url, json={'op': 'relink'}, auth_token='token')

        dbnode = self.get(url, auth_token='token').json()
        self.assertTrue(dbnode['properties']['used_in_edit'])

    @responses.activate
    def test_patch_relink_deleted(self):
        """Relinking a deleted shot should undelete it.

        We implement PATCH by changing then PUTing, which undeletes.
        """

        shot = self.create_shot()
        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')

        url = '/api/nodes/%s' % shot._id

        # Delete (and verify deletion)
        self.delete(url, auth_token='token',
                    headers={'If-Match': shot['_etag']},
                    expected_status=204)
        self.get(url, auth_token='token', expected_status=404)

        patch = {'op': 'relink'}
        self.patch(url, json=patch, auth_token='token')

        dbnode = self.get(url, auth_token='token').json()
        self.assertTrue(dbnode['properties']['used_in_edit'])


class RequiredAfterCreationTest(AbstractShotTest):
    """
    This tests Pillar stuff, but requires flamenco_shot since that's what the
    required_after_creation=False was created for.

    Placing the test here was easier than creating a node type in Pillar
    specifically for this test case. Once we use that validator in Pillar
    itself, we can move this test there too.
    """

    def test_create_shot(self):
        from flamenco.node_types import node_type_shot

        self.user_id = self.create_project_admin(self.project)
        self.create_valid_auth_token(self.user_id, 'token')

        node_type_name = node_type_shot['name']

        shot = {'name': u'test shot',
                'description': u'',
                'properties': {u'trim_start_in_frames': 0,
                               u'duration_in_edit_in_frames': 1,
                               u'cut_in_timeline_in_frames': 0},
                'node_type': node_type_name,
                'project': unicode(self.proj_id),
                'user': unicode(self.user_id)}

        resp = self.post('/api/nodes', json=shot,
                         auth_token='token', expected_status=201)
        info = resp.json()

        resp = self.get('/api/nodes/%(_id)s' % info, auth_token='token')
        json_shot = resp.json()

        self.assertEqual(node_type_shot['dyn_schema']['status']['default'],
                         json_shot['properties']['status'])

        return json_shot

    # TODO: should test editing a shot as well, but I had issues with the PillarSDK
    # not handling deleting of properties.


class ProjectSummaryTest(unittest.TestCase):

    def setUp(self):
        from flamenco.shots import ProjectSummary

        self.summ = ProjectSummary()
        self.summ.count(u'todo')
        self.summ.count(u'todo')
        self.summ.count(u'in-progress')
        self.summ.count(u'überhard')
        self.summ.count(u'Æon Flux')
        self.summ.count(u'Æon Flux')
        self.summ.count(u'in-progress')
        self.summ.count(u'todo')

    def test_counting(self):
        self.assertEqual(8, self.summ._total)
        self.assertEqual(3, self.summ._counts[u'todo'])
        self.assertEqual(2, self.summ._counts[u'Æon Flux'])

    def test_percentages(self):
        percs = list(self.summ.percentages())

        self.assertEqual((u'in-progress', 25), percs[0])
        self.assertEqual((u'todo', 38), percs[1])
        self.assertEqual((u'Æon Flux', 25), percs[2])

        # This should be rounded down, not rounded up, to ensure the sum of
        # percentages is 100.
        self.assertEqual((u'überhard', 12), percs[3])
