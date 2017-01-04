import unittest
import unittest.mock
from unittest.mock import Mock

import asyncio
import requests

from abstract_worker_test import AbstractWorkerTest


class AbstractFWorkerTest(AbstractWorkerTest):
    def setUp(self):
        from flamenco_worker.cli import construct_asyncio_loop
        from flamenco_worker.upstream import FlamencoManager
        from flamenco_worker.worker import FlamencoWorker
        from flamenco_worker.runner import TaskRunner
        from flamenco_worker.upstream_update_queue import TaskUpdateQueue

        self.asyncio_loop = construct_asyncio_loop()
        self.shutdown_future = self.asyncio_loop.create_future()

        self.manager = Mock(spec=FlamencoManager)
        self.trunner = Mock(spec=TaskRunner)
        self.tuqueue = Mock(spec=TaskUpdateQueue)

        self.trunner.execute = self.mock_task_execute

        self.worker = FlamencoWorker(
            manager=self.manager,
            trunner=self.trunner,
            tuqueue=self.tuqueue,
            job_types=['sleep', 'unittest'],
            worker_id='1234',
            worker_secret='jemoeder',
            loop=self.asyncio_loop,
            shutdown_future=self.shutdown_future,
        )

    def tearDown(self):
        self.shutdown_future.cancel()
        self.worker.shutdown()

    async def mock_task_execute(self, task: dict, fworker):
        """Mock task execute function that does nothing but sleep a bit."""

        await asyncio.sleep(1)
        return True


class WorkerStartupTest(AbstractFWorkerTest):
    # Mock merge_with_home_config() so that it doesn't overwrite actual config.
    @unittest.mock.patch('flamenco_worker.config.merge_with_home_config')
    def test_startup_already_registered(self, mock_merge_with_home_config):
        self.asyncio_loop.run_until_complete(self.worker.startup())
        mock_merge_with_home_config.assert_not_called()  # Starting with known ID/secret
        self.manager.post.assert_not_called()
        self.tuqueue.queue.assert_not_called()

    @unittest.mock.patch('flamenco_worker.config.merge_with_home_config')
    def test_startup_registration(self, mock_merge_with_home_config):
        from flamenco_worker.worker import detect_platform
        from mock_responses import JsonResponse, CoroMock

        self.worker.worker_id = None

        self.manager.post = CoroMock(return_value=JsonResponse({
            '_id': '5555',
        }))

        self.asyncio_loop.run_until_complete(self.worker.startup())
        mock_merge_with_home_config.assert_called_once_with(
            {'worker_id': '5555',
             'worker_secret': self.worker.worker_secret}
        )

        assert isinstance(self.manager.post, unittest.mock.Mock)
        self.manager.post.assert_called_once_with(
            '/register-worker',
            json={
                'platform': detect_platform(),
                'supported_job_types': ['sleep', 'unittest'],
                'secret': self.worker.worker_secret,
            },
            auth=None,
            loop=self.asyncio_loop,
        )

    @unittest.mock.patch('flamenco_worker.config.merge_with_home_config')
    def test_startup_registration_unhappy(self, mock_merge_with_home_config):
        """Test that startup is aborted when the worker can't register."""

        from flamenco_worker.worker import detect_platform
        from mock_responses import JsonResponse, CoroMock

        self.worker.worker_id = None

        self.manager.post = CoroMock(return_value=JsonResponse({
            '_id': '5555',
        }, status_code=500))

        # Mock merge_with_home_config() so that it doesn't overwrite actual config.
        self.assertRaises(requests.HTTPError,
                          self.asyncio_loop.run_until_complete,
                          self.worker.startup())
        mock_merge_with_home_config.assert_not_called()

        assert isinstance(self.manager.post, unittest.mock.Mock)
        self.manager.post.assert_called_once_with(
            '/register-worker',
            json={
                'platform': detect_platform(),
                'supported_job_types': ['sleep', 'unittest'],
                'secret': self.worker.worker_secret,
            },
            auth=None,
            loop=self.asyncio_loop,
        )


class TestWorkerTaskFetch(AbstractFWorkerTest):
    def setUp(self):
        super().setUp()
        from flamenco_worker.cli import construct_asyncio_loop

        self.loop = construct_asyncio_loop()
        self.worker.loop = self.loop

    def test_fetch_task_happy(self):
        from unittest.mock import call
        from mock_responses import JsonResponse, CoroMock

        self.manager.post = CoroMock()
        # response when fetching a task
        self.manager.post.coro.return_value = JsonResponse({
            '_id': '58514d1e9837734f2e71b479',
            'job': '58514d1e9837734f2e71b477',
            'manager': '585a795698377345814d2f68',
            'project': '',
            'user': '580f8c66983773759afdb20e',
            'name': 'sleep-14-26',
            'status': 'processing',
            'priority': 50,
            'job_type': 'sleep',
            'commands': [
                {'name': 'echo', 'settings': {'message': 'Preparing to sleep'}},
                {'name': 'sleep', 'settings': {'time_in_seconds': 3}}
            ]
        })

        async def async_none(): return None

        self.tuqueue.queue.side_effect = [
            # Responses after status updates
            None,  # task becoming active
            None,  # task becoming complete
        ]

        self.worker.schedule_fetch_task()
        self.manager.post.assert_not_called()

        interesting_task = self.worker.fetch_task_task
        self.loop.run_until_complete(self.worker.fetch_task_task)

        # Another fetch-task task should have been scheduled.
        self.assertNotEqual(self.worker.fetch_task_task, interesting_task)

        self.manager.post.assert_called_once_with('/task', loop=self.asyncio_loop)
        self.tuqueue.queue.assert_has_calls([
            call('/tasks/58514d1e9837734f2e71b479/update',
                 {'task_progress_percentage': 0, 'activity': '',
                  'command_progress_percentage': 0, 'task_status': 'active',
                  'current_command_idx': 0},
                 loop=self.loop,
                 ),
            call('/tasks/58514d1e9837734f2e71b479/update',
                 {'task_progress_percentage': 0, 'activity': '',
                  'command_progress_percentage': 0, 'task_status': 'completed',
                  'current_command_idx': 0},
                 loop=self.loop,
                 )
        ])
        self.assertEqual(self.tuqueue.queue.call_count, 2)
