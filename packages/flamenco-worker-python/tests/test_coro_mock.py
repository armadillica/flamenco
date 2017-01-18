"""Unit test for our CoroMock implementation."""

import asyncio
import unittest


class CoroMockTest(unittest.TestCase):
    def setUp(self):
        from flamenco_worker.cli import construct_asyncio_loop
        self.loop = construct_asyncio_loop()

    def test_setting_return_value(self):
        from mock_responses import CoroMock

        cm = CoroMock()
        cm.coro.return_value = '123'

        result = self.loop.run_until_complete(cm(3, 4))

        cm.assert_called_once_with(3, 4)
        self.assertEqual('123', result)
