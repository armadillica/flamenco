import unittest
from flask import url_for

from abstract_flamenco_test import AbstractFlamencoTest


class NotificationTest(AbstractFlamencoTest):
    """Test for startup and configuration notifications from the Manager."""
    # Old-style version 1 settings.
    notification_v1 = {
        'manager_url': 'https://flamenco.professional.farm/',
        'variables': {
            'blender': {'linux': '/shared/blender', 'windows': r'\\shared\blender.exe'},
            'ffmpeg': {'linux': '/shared/ffmpeg', 'windows': '//shared/ffmpeg.exe'},
        },
        'path_replacement': {
            'job_storage': {'linux': '/render/flamenco/storage', 'windows': 'R:/flamenco/storage'}
        },
        'nr_of_workers': 3,
        'worker_task_types': ['sleep', 'eat', 'blend', 'repeat'],
    }

    # Current-style (v2) version of the same settings as above.
    notification_v2 = {
        '_meta': {'version': 2},
        'manager_url': 'https://flamenco.professional.farm/',
        'variables': {
            'blender': {
                'direction': 'oneway',
                'values': [
                    {'audience': 'all', 'platform': 'linux',
                     'value': '/shared/blender'},
                    {'audience': 'all', 'platform': 'windows',
                     'value': r'\\shared\blender.exe'}]},
            'ffmpeg': {
                'direction': 'oneway',
                'values': [
                    {'audience': 'all', 'platform': 'linux',
                     'value': '/shared/ffmpeg'},
                    {'audience': 'all',
                     'platform': 'windows',
                     'value': '//shared/ffmpeg.exe'}]},
            'job_storage': {
                'direction': 'twoway',
                'values': [
                    {'audience': 'all', 'platform': 'linux',
                     'value': '/render/flamenco/storage'},
                    {'audience': 'all', 'platform': 'windows',
                     'value': 'R:/flamenco/storage'}]},
        },

        'nr_of_workers': 3,
        'worker_task_types': ['sleep', 'eat', 'blend', 'repeat'],
    }

    def setUp(self, **kwargs):
        super().setUp(**kwargs)

        mngr_doc, account, token = self.create_manager_service_account()
        self.mngr_id = mngr_doc['_id']
        self.mngr_doc = self.fetch_manager_from_db(self.mngr_id)
        self.mngr_token = token['token']

        self.create_user(user_id=24 * 'e', roles={'subscriber'}, token='user-token')

        with self.app.app_context():
            self.url = url_for('flamenco.managers.api.startup',
                               manager_id=str(self.mngr_id))

    def post_notification(self, notification):
        self.post(self.url, json=notification, auth_token=self.mngr_token, expected_status=204)

    def assertUntouched(self):
        db_man = self.fetch_manager_from_db(self.mngr_id)
        self.assertEqual(self.mngr_doc, db_man, 'Database should not have been touched')

    def test_empty_payload(self):
        self.post(self.url, json={}, auth_token=self.mngr_token, expected_status=400)
        self.assertUntouched()

    def test_partial_payload(self):
        resp = self.post(self.url, json={'manager_url': 'beh'},
                         auth_token=self.mngr_token, expected_status=400)
        self.assertIn('variables', resp.data.decode())
        self.assertUntouched()

    def test_other_token(self):
        self.post(self.url, json=self.notification_v2, auth_token='user-token', expected_status=403)
        self.assertUntouched()

    def test_notification_v1(self):
        notification = self.notification_v1
        self.post_notification(notification)

        db_man = self.fetch_manager_from_db(self.mngr_id)
        self.assertEqual(notification['manager_url'], db_man['url'])
        self.assertEqual(notification['variables'], db_man['variables'])
        self.assertEqual(notification['path_replacement'], db_man['path_replacement'])
        self.assertEqual(3, db_man['stats']['nr_of_workers'])
        self.assertEqual(notification['worker_task_types'], db_man['worker_task_types'])

    def test_notification_v2(self):
        notification = self.notification_v2
        self.post_notification(notification)

        db_man = self.fetch_manager_from_db(self.mngr_id)
        self.assertEqual(notification['_meta']['version'], db_man['settings_version'])
        self.assertEqual(notification['manager_url'], db_man['url'])
        self.assertEqual(notification['variables'], db_man['variables'])
        self.assertNotIn('path_replacement', db_man)
        self.assertEqual(3, db_man['stats']['nr_of_workers'])
        self.assertEqual(notification['worker_task_types'], db_man['worker_task_types'])

    def test_notification_v2_after_v1(self):
        self.post_notification(self.notification_v1)
        notification = self.notification_v2
        self.post_notification(notification)

        db_man = self.fetch_manager_from_db(self.mngr_id)
        self.assertEqual(notification['_meta']['version'], db_man['settings_version'])
        self.assertEqual(notification['manager_url'], db_man['url'])
        self.assertEqual(notification['variables'], db_man['variables'])
        self.assertNotIn('path_replacement', db_man)
        self.assertEqual(3, db_man['stats']['nr_of_workers'])
        self.assertEqual(notification['worker_task_types'], db_man['worker_task_types'])

    def test_without_worker_task_types(self):
        notification = self.notification_v1.copy()

        # This key was introduced recently, so many managers will not send it yet.
        del notification['worker_task_types']

        self.post_notification(notification)

        db_man = self.fetch_manager_from_db(self.mngr_id)
        self.assertEqual(notification['manager_url'], db_man['url'])
        self.assertEqual(notification['variables'], db_man['variables'])
        self.assertEqual(notification['path_replacement'], db_man['path_replacement'])
        self.assertEqual(3, db_man['stats']['nr_of_workers'])
        self.assertNotIn('worker_task_types', db_man)

    def test_schema_downgrade(self):
        notification = self.notification_v2
        self.post_notification(notification)

        with self.app.app_context():
            manager_url = url_for('flamenco_managers|item_lookup', _id=str(self.mngr_id))

        # This should give a v2 response back
        resp = self.get(manager_url, auth_token=self.mngr_token)
        json_manager = resp.json
        self.assertEqual(notification['_meta']['version'], json_manager['settings_version'])
        self.assertEqual(notification['variables'], json_manager['variables'])
        self.assertNotIn('path_replacement', json_manager)

        # This should give a v1 response back
        resp = self.get(manager_url, auth_token=self.mngr_token,
                        headers={'Blender-Cloud-Addon': '1.12.0'})
        json_manager = resp.json
        self.assertEqual(1, json_manager['settings_version'])
        self.assertEqual(self.notification_v1['variables'], json_manager['variables'])
        self.assertEqual(self.notification_v1['path_replacement'], json_manager['path_replacement'])
