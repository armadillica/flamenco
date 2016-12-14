from __future__ import absolute_import

import unittest
import mock
from bson import ObjectId


class SleepSimpleTest(unittest.TestCase):
    def test_job_compilation(self):
        from flamenco.job_compilers import sleep, commands

        job_doc = {
            '_id': ObjectId(24 * 'f'),
            'settings': {
                'frames': '1-30, 40-44',
                'chunk_size': 13,
                'time_in_seconds': 3,
            }
        }
        task_manager = mock.Mock()
        compiler = sleep.Sleep(task_manager=task_manager)
        compiler.compile(job_doc)

        task_manager.api_create_task.assert_has_calls([
            mock.call(
                job_doc,
                [
                    commands.Echo(message=u'Preparing to sleep'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-1-13',
            ),
            mock.call(
                job_doc,
                [
                    commands.Echo(message=u'Preparing to sleep'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-14-26',
            ),
            mock.call(
                job_doc,
                [
                    commands.Echo(message=u'Preparing to sleep'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-27-30,40-44',
            ),
        ])


class CommandTest(unittest.TestCase):
    def test_to_dict(self):
        from flamenco.job_compilers import commands

        cmd = commands.Echo(message=u'Preparing to sleep')
        self.assertEqual({
            'name': 'echo',
            'settings': {
                'message': u'Preparing to sleep',
            }
        }, cmd.to_dict())
