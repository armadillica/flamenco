import unittest
import unittest.mock
from unittest.mock import Mock

import asyncio
import requests
import attr


@attr.s
class JsonResponse:
    """Mocked HTTP response returning JSON.

    Maybe we want to switch to using unittest.mock.Mock for this,
    or to using the responses package.
    """

    _json = attr.ib()
    status_code = attr.ib(default=200, validator=attr.validators.instance_of(int))

    def json(self):
        return self._json

    def raise_for_status(self):
        if 200 <= self.status_code < 300:
            return

        raise requests.HTTPError(self.status_code)


@attr.s
class EmptyResponse:
    """Mocked HTTP response returning an empty 204.

    Maybe we want to switch to using unittest.mock.Mock for this,
    or to using the responses package.
    """

    status_code = attr.ib(default=204, validator=attr.validators.instance_of(int))

    def raise_for_status(self):
        pass


class AbstractWorkerTest(unittest.TestCase):
    def setUp(self):
        from flamenco_worker.upstream import FlamencoManager
        from flamenco_worker.worker import FlamencoWorker
        from flamenco_worker.runner import TaskRunner

        self.asyncio_loop = asyncio.get_event_loop()
        self.shutdown_future = self.asyncio_loop.create_future()

        self.manager = Mock(spec=FlamencoManager)
        self.trunner = Mock(spec=TaskRunner)

        self.trunner.execute = self.mock_task_execute

        self.worker = FlamencoWorker(
            manager=self.manager,
            trunner=self.trunner,
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


class WorkerStartupTest(AbstractWorkerTest):
    def test_startup_already_registered(self):
        self.worker.startup()
        self.manager.post.assert_not_called()

    def test_startup_registration(self):
        from flamenco_worker.worker import detect_platform

        self.worker.worker_id = None

        self.manager.post = Mock(return_value=JsonResponse({
            '_id': '5555',
        }))

        # Mock merge_with_home_config() so that it doesn't overwrite actual config.
        with unittest.mock.patch('flamenco_worker.config.merge_with_home_config'):
            self.worker.startup()

        assert isinstance(self.manager.post, unittest.mock.Mock)
        self.manager.post.assert_called_once_with(
            '/register-worker',
            json={
                'platform': detect_platform(),
                'supported_job_types': ['sleep', 'unittest'],
                'secret': self.worker.worker_secret,
            },
            auth=None,
        )

    def test_startup_registration_unhappy(self):
        """Test that startup is aborted when the worker can't register."""

        from flamenco_worker.worker import detect_platform

        self.worker.worker_id = None

        self.manager.post = unittest.mock.Mock(return_value=JsonResponse({
            '_id': '5555',
        }, status_code=500))

        # Mock merge_with_home_config() so that it doesn't overwrite actual config.
        with unittest.mock.patch('flamenco_worker.config.merge_with_home_config'):
            self.assertRaises(requests.HTTPError, self.worker.startup)

        assert isinstance(self.manager.post, unittest.mock.Mock)
        self.manager.post.assert_called_once_with(
            '/register-worker',
            json={
                'platform': detect_platform(),
                'supported_job_types': ['sleep', 'unittest'],
                'secret': self.worker.worker_secret,
            },
            auth=None,
        )


class TestWorkerTaskFetch(AbstractWorkerTest):
    def setUp(self):
        super().setUp()
        self.loop = asyncio.get_event_loop()
        self.worker.loop = self.loop

    def run_loop_for(self, seconds: float):
        """Runs the loop for 'seconds' seconds."""

        async def stop_loop():
            await asyncio.sleep(seconds)
            self.loop.stop()

        self.loop.run_until_complete(stop_loop())

    def test_fetch_task_happy(self):
        from unittest.mock import call

        self.manager.post = Mock()
        self.manager.post.side_effect = [
            # response when fetching a task
            JsonResponse({
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
            }),
            # Responses after status updates
            EmptyResponse(),  # task becoming active
            EmptyResponse(),  # task becoming complete
        ]

        self.worker.schedule_fetch_task()
        self.manager.post.assert_not_called()

        interesting_task = self.worker.fetch_task_task
        self.loop.run_until_complete(self.worker.fetch_task_task)

        # Another fetch-task task should have been scheduled.
        self.assertNotEqual(self.worker.fetch_task_task, interesting_task)

        self.manager.post.assert_has_calls([
            call('/task'),
            call('/tasks/58514d1e9837734f2e71b479/update',
                 json={'task_progress_percentage': 0, 'activity': '',
                       'command_progress_percentage': 0, 'task_status': 'active',
                       'current_command_idx': 0},
                 ),
            call('/tasks/58514d1e9837734f2e71b479/update',
                 json={'task_progress_percentage': 0, 'activity': '',
                       'command_progress_percentage': 0, 'task_status': 'completed',
                       'current_command_idx': 0},
                 ),
        ])
        self.assertEqual(self.manager.post.call_count, 3)
