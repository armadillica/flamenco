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
        from mock_responses import CoroMock

        self.asyncio_loop = construct_asyncio_loop()
        self.asyncio_loop.set_debug(True)
        self.shutdown_future = self.asyncio_loop.create_future()

        self.manager = Mock(spec=FlamencoManager)
        self.manager.post = CoroMock()

        self.trunner = Mock(spec=TaskRunner)
        self.tuqueue = Mock(spec=TaskUpdateQueue)
        self.tuqueue.flush_for_shutdown = CoroMock()

        self.trunner.execute = self.mock_task_execute
        self.trunner.abort_current_task = CoroMock()

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
        self.asyncio_loop.close()

    async def mock_task_execute(self, task: dict, fworker):
        """Mock task execute function that does nothing but sleep a bit."""

        await asyncio.sleep(1)
        return True


class WorkerStartupTest(AbstractFWorkerTest):
    # Mock merge_with_home_config() so that it doesn't overwrite actual config.
    @unittest.mock.patch('flamenco_worker.config.merge_with_home_config')
    def test_startup_already_registered(self, mock_merge_with_home_config):
        self.asyncio_loop.run_until_complete(self.worker.startup(may_retry_register=False))
        mock_merge_with_home_config.assert_not_called()  # Starting with known ID/secret
        self.manager.post.assert_not_called()
        self.tuqueue.queue.assert_not_called()

    @unittest.mock.patch('socket.gethostname')
    @unittest.mock.patch('flamenco_worker.config.merge_with_home_config')
    def test_startup_registration(self, mock_merge_with_home_config, mock_gethostname):
        from flamenco_worker.worker import detect_platform
        from mock_responses import JsonResponse, CoroMock

        self.worker.worker_id = None
        mock_gethostname.return_value = 'ws-unittest'

        self.manager.post = CoroMock(return_value=JsonResponse({
            '_id': '5555',
        }))

        self.asyncio_loop.run_until_complete(self.worker.startup(may_retry_register=False))
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
                'nickname': 'ws-unittest',
            },
            auth=None,
            loop=self.asyncio_loop,
        )

    @unittest.mock.patch('socket.gethostname')
    @unittest.mock.patch('flamenco_worker.config.merge_with_home_config')
    def test_startup_registration_unhappy(self, mock_merge_with_home_config, mock_gethostname):
        """Test that startup is aborted when the worker can't register."""

        from flamenco_worker.worker import detect_platform, UnableToRegisterError
        from mock_responses import JsonResponse, CoroMock

        self.worker.worker_id = None
        mock_gethostname.return_value = 'ws-unittest'

        self.manager.post = CoroMock(return_value=JsonResponse({
            '_id': '5555',
        }, status_code=500))

        # Mock merge_with_home_config() so that it doesn't overwrite actual config.
        self.assertRaises(UnableToRegisterError,
                          self.asyncio_loop.run_until_complete,
                          self.worker.startup(may_retry_register=False))
        mock_merge_with_home_config.assert_not_called()

        assert isinstance(self.manager.post, unittest.mock.Mock)
        self.manager.post.assert_called_once_with(
            '/register-worker',
            json={
                'platform': detect_platform(),
                'supported_job_types': ['sleep', 'unittest'],
                'secret': self.worker.worker_secret,
                'nickname': 'ws-unittest',
            },
            auth=None,
            loop=self.asyncio_loop,
        )


class TestWorkerTaskExecution(AbstractFWorkerTest):
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
                 {'task_progress_percentage': 0, 'activity': 'Task completed',
                  'command_progress_percentage': 0, 'task_status': 'completed',
                  'current_command_idx': 0},
                 loop=self.loop,
                 )
        ])
        self.assertEqual(self.tuqueue.queue.call_count, 2)

    def test_stop_current_task(self):
        """Test that stopped tasks get status 'canceled'."""

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
                {'name': 'sleep', 'settings': {'time_in_seconds': 3}}
            ]
        })

        self.worker.schedule_fetch_task()

        stop_called = False
        async def stop():
            nonlocal stop_called
            stop_called = True

            await asyncio.sleep(0.2)
            await self.worker.stop_current_task()

        asyncio.ensure_future(stop(), loop=self.loop)
        self.loop.run_until_complete(self.worker.fetch_task_task)

        self.assertTrue(stop_called)

        self.manager.post.assert_called_once_with('/task', loop=self.asyncio_loop)
        self.tuqueue.queue.assert_has_calls([
            call('/tasks/58514d1e9837734f2e71b479/update',
                 {'task_progress_percentage': 0, 'activity': '',
                  'command_progress_percentage': 0, 'task_status': 'active',
                  'current_command_idx': 0},
                 loop=self.loop,
                 ),
            call('/tasks/58514d1e9837734f2e71b479/update',
                 {'task_progress_percentage': 0, 'activity': 'Task was canceled',
                  'command_progress_percentage': 0, 'task_status': 'canceled',
                  'current_command_idx': 0},
                 loop=self.loop,
                 )
        ])
        self.assertEqual(self.tuqueue.queue.call_count, 2)


class WorkerPushToMasterTest(AbstractFWorkerTest):
    def test_one_activity(self):
        """A single activity should be sent to manager within reasonable time."""

        from datetime import timedelta

        queue_pushed_future = asyncio.Future()

        def queue_pushed(*args, **kwargs):
            queue_pushed_future.set_result(True)

        self.tuqueue.queue.side_effect = queue_pushed
        self.worker.push_act_max_interval = timedelta(milliseconds=500)

        asyncio.ensure_future(
            self.worker.register_task_update(activity='test'),
            loop=self.asyncio_loop)

        self.asyncio_loop.run_until_complete(
            asyncio.wait_for(queue_pushed_future, 1))

        # Queue push should only be done once
        self.assertEqual(self.tuqueue.queue.call_count, 1)

    def test_two_activities(self):
        """A single non-status-changing and then a status-changing act should push once."""

        from datetime import timedelta

        queue_pushed_future = asyncio.Future()

        def queue_pushed(*args, **kwargs):
            queue_pushed_future.set_result(True)

        self.tuqueue.queue.side_effect = queue_pushed
        self.worker.push_act_max_interval = timedelta(milliseconds=500)

        # Non-status-changing
        asyncio.ensure_future(
            self.worker.register_task_update(activity='test'),
            loop=self.asyncio_loop)

        # Status-changing
        asyncio.ensure_future(
            self.worker.register_task_update(task_status='changed'),
            loop=self.asyncio_loop)

        self.asyncio_loop.run_until_complete(
            asyncio.wait_for(queue_pushed_future, 1))

        # Queue push should only be done once
        self.assertEqual(self.tuqueue.queue.call_count, 1)

        # The scheduled task should be cancelled.
        self.assertTrue(self.worker._push_act_to_manager.cancelled())

    def test_one_log(self):
        """A single log should be sent to manager within reasonable time."""

        from datetime import timedelta

        queue_pushed_future = asyncio.Future()

        def queue_pushed(*args, **kwargs):
            queue_pushed_future.set_result(True)

        self.tuqueue.queue.side_effect = queue_pushed
        self.worker.push_log_max_interval = timedelta(milliseconds=500)

        asyncio.ensure_future(
            self.worker.register_log('unit tests are ünits'),
            loop=self.asyncio_loop)

        self.asyncio_loop.run_until_complete(
            asyncio.wait_for(queue_pushed_future, 1))

        # Queue push should only be done once
        self.assertEqual(self.tuqueue.queue.call_count, 1)

    def test_two_logs(self):
        """Logging once and then again should push once."""

        queue_pushed_future = asyncio.Future()

        def queue_pushed(*args, **kwargs):
            queue_pushed_future.set_result(True)

        self.tuqueue.queue.side_effect = queue_pushed
        self.worker.push_log_max_entries = 1  # max 1 queued, will push at 2

        # Queued, will schedule push
        asyncio.ensure_future(
            self.worker.register_log('first line'),
            loop=self.asyncio_loop)

        # Max queued reached, will cause immediate push
        asyncio.ensure_future(
            self.worker.register_log('second line'),
            loop=self.asyncio_loop)

        self.asyncio_loop.run_until_complete(
            asyncio.wait_for(queue_pushed_future, 1))

        # Queue push should only be done once
        self.assertEqual(self.tuqueue.queue.call_count, 1)

        # The scheduled task should be cancelled.
        self.assertTrue(self.worker._push_log_to_manager.cancelled())



class WorkerShutdownTest(AbstractWorkerTest):
    def setUp(self):
        from flamenco_worker.cli import construct_asyncio_loop
        from flamenco_worker.upstream import FlamencoManager
        from flamenco_worker.worker import FlamencoWorker
        from flamenco_worker.runner import TaskRunner
        from flamenco_worker.upstream_update_queue import TaskUpdateQueue
        from mock_responses import CoroMock

        self.asyncio_loop = construct_asyncio_loop()
        self.asyncio_loop.set_debug(True)
        self.shutdown_future = self.asyncio_loop.create_future()

        self.manager = Mock(spec=FlamencoManager)
        self.manager.post = CoroMock()

        self.trunner = Mock(spec=TaskRunner)
        self.tuqueue = Mock(spec=TaskUpdateQueue)
        self.tuqueue.flush_for_shutdown = CoroMock()
        self.trunner.abort_current_task = CoroMock()

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

    def test_shutdown(self):
        self.shutdown_future.cancel()
        self.worker.shutdown()

        self.manager.post.assert_called_once_with('/sign-off', loop=self.asyncio_loop)

    def tearDown(self):
        self.asyncio_loop.close()
