"""Unit test for our CoroMock implementation."""

import asyncio
import unittest


class CoroMockTest(unittest.TestCase):
    def test_setting_return_value(self):
        from mock_responses import CoroMock

        cm = CoroMock()
        cm.coro.return_value = '123'

        result = asyncio.get_event_loop().run_until_complete(cm(3, 4))

        cm.assert_called_once_with(3, 4)
        self.assertEqual('123', result)
