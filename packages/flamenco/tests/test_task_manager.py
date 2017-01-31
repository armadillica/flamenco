# -*- encoding: utf-8 -*-
from __future__ import absolute_import

from pillar.tests import common_test_data as ctd
from abstract_flamenco_test import AbstractFlamencoTest


class TaskManagerTest(AbstractFlamencoTest):
    def test_create_task(self):
        from pillar.api.utils.authentication import force_cli_user
        from flamenco.job_compilers import commands

        manager, _, _ = self.create_manager_service_account()

        with self.app.test_request_context():
            force_cli_user()
            job_doc = self.jmngr.api_create_job(
                'test job',
                u'Wörk wørk w°rk.',
                'sleep', {
                    'frames': '12-18, 20-22',
                    'chunk_size': 7,
                    'time_in_seconds': 3,
                },
                self.proj_id,
                ctd.EXAMPLE_PROJECT_OWNER_ID,
                manager['_id'],
            )

            self.tmngr.api_create_task(
                job_doc,
                [
                    commands.Echo(message=u'ẑžƶźz'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-1-13',
            )

        # Now test the database contents.
        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            dbtasks = list(tasks_coll.find())
            self.assertEqual(3, len(dbtasks))  # 2 of compiled job + the one we added after.

            dbtask = dbtasks[-1]

            self.assertEqual({
                u'name': u'echo',
                u'settings': {
                    u'message': u'ẑžƶźz',
                }
            }, dbtask['commands'][0])

            self.assertEqual({
                u'name': u'sleep',
                u'settings': {
                    u'time_in_seconds': 3,
                }
            }, dbtask['commands'][1])

    def test_api_find_jobfinal_tasks(self):
        from pillar.api.utils.authentication import force_cli_user
        from flamenco.job_compilers import commands

        manager, _, _ = self.create_manager_service_account()

        with self.app.test_request_context():
            force_cli_user()
            job_doc = self.jmngr.api_create_job(
                'test job',
                u'Wörk wørk w°rk.',
                'sleep', {
                    'frames': '12-18, 20-22',
                    'chunk_size': 7,
                    'time_in_seconds': 3,
                },
                self.proj_id,
                ctd.EXAMPLE_PROJECT_OWNER_ID,
                manager['_id'],
            )
            job_id = job_doc['_id']

            # Find the tasks created so far, use them as parents.
            tasks = self.flamenco.db('tasks').find({'job': job_id},
                                                   projection={'_id': 1})
            task_ids = [t['_id'] for t in tasks]

            # dependent task that is used as a single parent.
            taskid1 = self.tmngr.api_create_task(
                job_doc, [commands.Echo(message=u'ẑžƶźz')], 'zzz 1', parents=task_ids,
            )

            # task dependent on multiple tasks that is not used as a parent.
            taskid2 = self.tmngr.api_create_task(
                job_doc, [commands.Echo(message=u'ẑžƶźz')], 'zzz 2', parents=task_ids,
            )

            # task dependent on a single task that is not used as a parent.
            taskid3 = self.tmngr.api_create_task(
                job_doc, [commands.Echo(message=u'ẑžƶźz')], 'zzz 3', parents=[taskid1],
            )

            # independent task
            taskid4 = self.tmngr.api_create_task(
                job_doc, [commands.Echo(message=u'ẑžƶźz')], 'zzz 4',
            )

            job_enders = self.tmngr.api_find_job_enders(job_id)
            self.assertEqual({taskid2, taskid3, taskid4}, set(job_enders))
