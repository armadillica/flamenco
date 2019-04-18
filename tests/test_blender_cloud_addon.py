import unittest
from unittest import mock

import werkzeug.exceptions as wz_exceptions


@mock.patch('flask.request')
class RequestedByVersionTest(unittest.TestCase):

    def test_not_addon(self, mock_request):
        from flamenco import blender_cloud_addon as bca

        mock_request.headers = {}
        self.assertIsNone(bca.requested_by_version())

    def test_happy(self, mock_request):
        from flamenco import blender_cloud_addon as bca

        mock_request.headers = {'Blender-Cloud-Addon': '1.12.3'}
        self.assertEqual((1, 12, 3), bca.requested_by_version())

        mock_request.headers = {'Blender-Cloud-Addon': '1.12'}
        self.assertEqual((1, 12, 0), bca.requested_by_version())

    def test_wrong_digit_count(self, mock_request):
        from flamenco import blender_cloud_addon as bca

        mock_request.headers = {'Blender-Cloud-Addon': '1.12.3.4'}
        with self.assertRaises(wz_exceptions.BadRequest):
            bca.requested_by_version()

        mock_request.headers = {'Blender-Cloud-Addon': '1'}
        with self.assertRaises(wz_exceptions.BadRequest):
            bca.requested_by_version()

    def test_not_numerical(self, mock_request):
        from flamenco import blender_cloud_addon as bca

        mock_request.headers = {'Blender-Cloud-Addon': '1.12.beta2'}
        with self.assertRaises(wz_exceptions.BadRequest):
            bca.requested_by_version()

    def test_no_dot(self, mock_request):
        from flamenco import blender_cloud_addon as bca

        mock_request.headers = {'Blender-Cloud-Addon': 'je moeder'}
        with self.assertRaises(wz_exceptions.BadRequest):
            bca.requested_by_version()
