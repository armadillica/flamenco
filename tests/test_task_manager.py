# -*- encoding: utf-8 -*-

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
                'Wörk wørk w°rk.',
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
                    commands.Echo(message='ẑžƶźz'),
                    commands.Sleep(time_in_seconds=3),
                ],
                'sleep-1-13',
                status='under-construction'
            )

        # Now test the database contents.
        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')
            dbtasks = list(tasks_coll.find())
            self.assertEqual(3, len(dbtasks))  # 2 of compiled job + the one we added after.

            statuses = [task['status'] for task in dbtasks]
            self.assertEqual(['queued', 'queued', 'under-construction'], statuses)

            dbtask = dbtasks[-1]

            self.assertEqual({
                'name': 'echo',
                'settings': {
                    'message': 'ẑžƶźz',
                }
            }, dbtask['commands'][0])

            self.assertEqual({
                'name': 'sleep',
                'settings': {
                    'time_in_seconds': 3,
                }
            }, dbtask['commands'][1])

        return job_doc['_id']

    def test_api_find_jobfinal_tasks(self):
        from pillar.api.utils.authentication import force_cli_user
        from flamenco.job_compilers import commands

        manager, _, _ = self.create_manager_service_account()

        with self.app.test_request_context():
            force_cli_user()
            job_doc = self.jmngr.api_create_job(
                'test job',
                'Wörk wørk w°rk.',
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
                job_doc, [commands.Echo(message='ẑžƶźz')], 'zzz 1', parents=task_ids,
            )

            # task dependent on multiple tasks that is not used as a parent.
            taskid2 = self.tmngr.api_create_task(
                job_doc, [commands.Echo(message='ẑžƶźz')], 'zzz 2', parents=task_ids,
            )

            # task dependent on a single task that is not used as a parent.
            taskid3 = self.tmngr.api_create_task(
                job_doc, [commands.Echo(message='ẑžƶźz')], 'zzz 3', parents=[taskid1],
            )

            # independent task
            taskid4 = self.tmngr.api_create_task(
                job_doc, [commands.Echo(message='ẑžƶźz')], 'zzz 4',
            )

            job_enders = self.tmngr.api_find_job_enders(job_id)
            self.assertEqual({taskid2, taskid3, taskid4}, set(job_enders))

    def test_api_set_task_status_for_job(self):
        import time

        # Create some tasks to flip.
        job_id = self.test_create_task()

        with self.app.test_request_context():
            tasks_coll = self.flamenco.db('tasks')

            db_tasks = list(tasks_coll.find())
            statuses = [task['status'] for task in db_tasks]
            pre_flip_updated = [task['_updated'] for task in db_tasks]
            pre_flip_etags = [task['_etag'] for task in db_tasks]
            self.assertEqual(['queued', 'queued', 'under-construction'], statuses)

            # Sleep a bit so we can check the change in _updated fields.
            time.sleep(1)

            # Flip and re-check the status.
            self.tmngr.api_set_task_status_for_job(job_id, 'queued', 'active')

            db_tasks = list(tasks_coll.find())
            statuses = [task['status'] for task in db_tasks]
            post_flip_updated = [task['_updated'] for task in db_tasks]
            post_flip_etags = [task['_etag'] for task in db_tasks]
            self.assertEqual(['active', 'active', 'under-construction'], statuses)

            # Check changed timestamps.
            self.assertLess(pre_flip_updated[0], post_flip_updated[0])
            self.assertLess(pre_flip_updated[1], post_flip_updated[1])
            self.assertEqual(pre_flip_updated[2], post_flip_updated[2])

            # Check changed etags.
            self.assertNotEqual(pre_flip_etags[0], post_flip_etags[0])
            self.assertNotEqual(pre_flip_etags[1], post_flip_etags[1])
            self.assertEqual(pre_flip_etags[2], post_flip_etags[2])

    def test_api_set_activity(self):
        job_id = self.test_create_task()

        # Ensure we have three activities:
        #   - non-existent
        #   - empty string
        #   - non-empty string
        with self.app.test_request_context():
            tasks_coll = self.tmngr.collection()
            dbtasks = list(tasks_coll.find())
            self.assertEqual(3, len(dbtasks))  # 2 of compiled job + the one we added after.

            tasks_coll.update_one({'_id': dbtasks[0]['_id']}, {'$unset': {'activity': ''}})
            tasks_coll.update_one({'_id': dbtasks[1]['_id']}, {'$set': {'activity': ''}})
            tasks_coll.update_one({'_id': dbtasks[2]['_id']}, {'$set': {'activity': 'Trés active'}})

            # Set a new activity
            self.tmngr.api_set_activity(
                {'job': job_id,
                 'activity': {'$exists': False}},
                'Activiteit geüpdated.'
            )

            # Test the result
            dbtasks = list(self.tmngr.collection().find())
            self.assertEqual('Activiteit geüpdated.', dbtasks[0]['activity'])
            self.assertEqual('', dbtasks[1]['activity'])
            self.assertEqual('Trés active', dbtasks[2]['activity'])
