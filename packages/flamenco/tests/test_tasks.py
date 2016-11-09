# -*- encoding: utf-8 -*-

import responses
from bson import ObjectId

import pillarsdk
import pillarsdk.exceptions as sdk_exceptions
import pillar.api.utils
import pillar.tests
import pillar.auth
import pillar.tests.common_test_data as ctd

from abstract_attract_test import AbstractAttractTest
from pillarsdk.utils import remove_private_keys


class TaskWorkflowTest(AbstractAttractTest):
    def setUp(self, **kwargs):
        AbstractAttractTest.setUp(self, **kwargs)

        self.mngr = self.app.pillar_extensions['attract'].task_manager
        self.proj_id, self.project = self.ensure_project_exists()

        self.sdk_project = pillarsdk.Project(pillar.tests.mongo_to_sdk(self.project))

    def create_task(self, task_type=None, parent=None):
        with self.app.test_request_context():
            # Log in as project admin user
            pillar.auth.login_user(ctd.EXAMPLE_PROJECT_OWNER_ID)

            self.mock_blenderid_validate_happy()
            task = self.mngr.create_task(self.sdk_project, task_type=task_type, parent=parent)

        self.assertIsInstance(task, pillarsdk.Node)
        return task

    @responses.activate
    def test_create_task(self):
        task = self.create_task(task_type=u'Just düüüh it')
        self.assertIsNotNone(task)

        # Test directly with MongoDB
        with self.app.test_request_context():
            nodes_coll = self.app.data.driver.db['nodes']
            found = nodes_coll.find_one(ObjectId(task['_id']))
            self.assertIsNotNone(found)
        self.assertEqual(u'Just düüüh it', found['properties']['task_type'])

        # Test it through the API
        resp = self.get('/api/nodes/%s' % task['_id'])
        found = resp.json()
        self.assertEqual(u'Just düüüh it', found['properties']['task_type'])

    @responses.activate
    def test_edit_task(self):
        task = self.create_task()

        with self.app.test_request_context():
            # Log in as project admin user
            pillar.auth.login_user(ctd.EXAMPLE_PROJECT_OWNER_ID)

            self.mock_blenderid_validate_happy()
            self.assertRaises(sdk_exceptions.PreconditionFailed,
                              self.mngr.edit_task,
                              task._id,
                              task_type=u'je møder',
                              name=u'nööw name',
                              description=u'€ ≠ ¥',
                              status='todo',
                              _etag='jemoeder')
            self.mngr.edit_task(task._id,
                                task_type=u'je møder',
                                name=u'nööw name',
                                description=u'€ ≠ ¥',
                                status='todo',
                                _etag=task._etag)

        # Test directly with MongoDB
        with self.app.test_request_context():
            nodes_coll = self.app.data.driver.db['nodes']
            found = nodes_coll.find_one(ObjectId(task['_id']))
            self.assertEqual(u'je møder', found['properties']['task_type'])
            self.assertEqual(u'todo', found['properties']['status'])
            self.assertEqual(u'nööw name', found['name'])
            self.assertEqual(u'€ ≠ ¥', found['description'])

    @responses.activate
    def test_load_save_task(self):
        """Test for the Eve hooks -- we should be able to PUT what we GET."""

        task_parent = self.create_task(task_type=u'Just düüüh it')
        task_child = self.create_task(task_type=u'mamaaaah',
                                      parent=task_parent['_id'])

        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')

        url = '/api/nodes/%s' % task_child['_id']
        resp = self.get(url)
        json_task = resp.json()

        self.put(url,
                 json=remove_private_keys(json_task),
                 auth_token='token',
                 headers={'If-Match': json_task['_etag']})

    @responses.activate
    def test_delete_task(self):
        task = self.create_task()
        task_id = task['_id']

        self.create_valid_auth_token(ctd.EXAMPLE_PROJECT_OWNER_ID, 'token')
        node_url = '/api/nodes/%s' % task_id
        self.get(node_url, auth_token='token')

        with self.app.test_request_context():
            # Log in as project admin user
            pillar.auth.login_user(ctd.EXAMPLE_PROJECT_OWNER_ID)

            self.mock_blenderid_validate_happy()
            self.assertRaises(sdk_exceptions.PreconditionFailed,
                              self.mngr.delete_task,
                              task._id,
                              'jemoeder')
            self.mngr.delete_task(task._id, task._etag)

        # Test directly with MongoDB
        with self.app.test_request_context():
            nodes_coll = self.app.data.driver.db['nodes']
            found = nodes_coll.find_one(ObjectId(task_id))
            self.assertTrue(found['_deleted'])

        # Test with Eve
        self.get(node_url, auth_token='token', expected_status=404)
