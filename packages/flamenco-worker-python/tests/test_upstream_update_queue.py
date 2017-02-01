import asyncio
import copy
import datetime
import tempfile
from unittest.mock import Mock

import requests

from abstract_worker_test import AbstractWorkerTest


class TaskUpdateQueueTest(AbstractWorkerTest):
    def setUp(self):
        from flamenco_worker.upstream import FlamencoManager
        from flamenco_worker.upstream_update_queue import TaskUpdateQueue
        from flamenco_worker.cli import construct_asyncio_loop
        from mock_responses import CoroMock

        self.asyncio_loop = construct_asyncio_loop()
        self.shutdown_future = self.asyncio_loop.create_future()

        self.manager = Mock(spec=FlamencoManager)
        self.manager.post = CoroMock()

        self.tmpdir = tempfile.TemporaryDirectory()
        self.tuqueue = TaskUpdateQueue(
            db_fname='%s/unittest.db' % self.tmpdir.name,
            manager=self.manager,
            shutdown_future=self.shutdown_future,
            backoff_time=0.3,  # faster retry to keep the unittest speedy.
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_queue_push(self):
        """Test that a queue() is followed by an actual push to Flamenco Manager.

        Also tests connection errors and other HTTP error statuses.
        """

        from mock_responses import JsonResponse, EmptyResponse

        # Try different value types
        payload = {'key': 'value',
                   'sub': {'some': 13,
                           'values': datetime.datetime.now()}}

        tries = 0
        received_payload = None
        received_url = None
        received_loop = None

        async def push_callback(url, *, json, loop):
            nonlocal tries
            nonlocal received_url
            nonlocal received_payload
            nonlocal received_loop

            tries += 1
            if tries < 3:
                raise requests.ConnectionError()
            if tries == 3:
                return JsonResponse({}, status_code=500)

            # Shut down after handling this push.
            self.shutdown_future.cancel()

            # Remember what we received. Calling self.assertEqual() here doesn't stop the unittest,
            # since the work loop is designed to keep running, even when exceptions are thrown.
            received_url = url
            received_payload = copy.deepcopy(json)
            received_loop = loop

            return EmptyResponse()

        self.manager.post.side_effect = push_callback

        self.tuqueue.queue('/push/here', payload, loop=self.asyncio_loop)

        # Run the loop for 2 seconds. This should be enough for 3 retries of 0.3 seconds + handling
        # the actual payload.
        self.asyncio_loop.run_until_complete(
            asyncio.wait_for(
                self.tuqueue.work(loop=self.asyncio_loop),
                timeout=2
            )
        )

        # Check the payload.
        self.assertEqual(received_url, '/push/here')
        self.assertEqual(received_payload, payload)
        self.assertEqual(received_loop, self.asyncio_loop)

    def test_queue_persistence(self):
        """Check that updates are pushed, even when the process is stopped & restarted."""

        from mock_responses import EmptyResponse
        from flamenco_worker.upstream_update_queue import TaskUpdateQueue

        # Try different value types
        payload = {'key': 'value',
                   'sub': {'some': 13,
                           'values': datetime.datetime.now()}}
        self.asyncio_loop.run_until_complete(
            self.tuqueue.queue('/push/there', payload, loop=self.asyncio_loop))
        self.manager.post.assert_not_called()
        self.tuqueue._disconnect_db()

        # Create a new tuqueue to handle the push, using the same database.
        # Note that we don't have to stop self.tuqueue because we never ran self.tuqueue.work().
        new_tuqueue = TaskUpdateQueue(
            db_fname=self.tuqueue.db_fname,
            manager=self.manager,
            shutdown_future=self.shutdown_future,
            backoff_time=5,  # no retry in this test, so any retry should cause a timeout.
        )

        received_payload = None
        received_url = None
        received_loop = None

        async def push_callback(url, *, json, loop):
            nonlocal received_url
            nonlocal received_payload
            nonlocal received_loop

            # Shut down after handling this push.
            self.shutdown_future.cancel()

            received_url = url
            received_payload = copy.deepcopy(json)
            received_loop = loop
            return EmptyResponse()

        self.manager.post.side_effect = push_callback

        # This should pick up on the pushed data.
        self.asyncio_loop.run_until_complete(
            asyncio.wait_for(
                new_tuqueue.work(loop=self.asyncio_loop),
                timeout=2
            )
        )

        # Check the payload
        self.assertEqual(received_url, '/push/there')
        self.assertEqual(received_payload, payload)
        self.assertEqual(received_loop, self.asyncio_loop)

    def test_conflict(self):
        """A 409 Conflict response should discard a queued task update.
        """

        from mock_responses import JsonResponse, EmptyResponse

        # Try different value types
        payload = {'key': 'value',
                   'sub': {'some': 13,
                           'values': datetime.datetime.now()}}

        tries = 0

        async def push_callback(url, *, json, loop):
            nonlocal tries
            tries += 1
            self.shutdown_future.cancel()
            return JsonResponse({}, status_code=409)

        self.manager.post.side_effect = push_callback

        self.tuqueue.queue('/push/here', payload, loop=self.asyncio_loop)

        # Run the loop for 2 seconds. This should be enough for 3 retries of 0.3 seconds + handling
        # the actual payload.
        self.asyncio_loop.run_until_complete(
            asyncio.wait_for(
                self.tuqueue.work(loop=self.asyncio_loop),
                timeout=2
            )
        )

        # There should only be one attempt at delivering this payload.
        self.assertEqual(1, tries)
        self.assertEqual([], list(self.tuqueue._queue()))
