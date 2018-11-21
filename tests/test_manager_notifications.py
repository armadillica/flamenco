from flask import url_for

from abstract_flamenco_test import AbstractFlamencoTest


class NotificationTest(AbstractFlamencoTest):
    """Test for startup and configuration notifications from the Manager."""
    notification = {
        'manager_url': 'https://flamenco.professional.farm/',
        'variables': {
            'linux': {'blender': '/shared/blender', 'ffmpeg': '/shared/ffmpeg'},
            'windows': {'blender': '//shared/blender.exe', 'ffmpeg': '//shared/ffmpeg.exe'},
        },
        'path_replacement': {},
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
        self.post(self.url, json=self.notification, auth_token='user-token', expected_status=403)
        self.assertUntouched()

    def test_startup_notification(self):
        notification = self.notification
        self.post_notification(notification)

        db_man = self.fetch_manager_from_db(self.mngr_id)
        self.assertEqual(notification['manager_url'], db_man['url'])
        self.assertEqual(notification['variables'], db_man['variables'])
        self.assertEqual(notification['path_replacement'], db_man['path_replacement'])
        self.assertEqual(3, db_man['stats']['nr_of_workers'])
        self.assertEqual(notification['worker_task_types'], db_man['worker_task_types'])

    def test_without_worker_task_types(self):
        notification = self.notification.copy()

        # This key was introduced recently, so many managers will not send it yet.
        del notification['worker_task_types']

        self.post_notification(notification)

        db_man = self.fetch_manager_from_db(self.mngr_id)
        self.assertEqual(notification['manager_url'], db_man['url'])
        self.assertEqual(notification['variables'], db_man['variables'])
        self.assertEqual(notification['path_replacement'], db_man['path_replacement'])
        self.assertEqual(3, db_man['stats']['nr_of_workers'])
        self.assertNotIn('worker_task_types', db_man)
