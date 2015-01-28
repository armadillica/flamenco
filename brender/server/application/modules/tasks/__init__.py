import os
import logging
from PIL import Image
from platform import system
from threading import Thread
from sqlalchemy import func

from flask import abort
from flask import jsonify
from flask import render_template
from flask import request
from flask.ext.restful import Resource
from flask.ext.restful import reqparse

from application import app
from application import db

from application.utils import http_rest_request
from application.utils import get_file_ext

from application.modules.tasks.model import Task
from application.modules.managers.model import Manager
from application.modules.jobs.model import Job
from application.modules.projects.model import Project
from application.modules.settings.model import Setting
from application.modules.jobs.model import JobManagers


parser = reqparse.RequestParser()
parser.add_argument('id', type=int)
parser.add_argument('status', type=str)


class TaskApi(Resource):
    @staticmethod
    def create_task(job_id, chunk_start, chunk_end):
        # TODO attribution of the best manager
        task = Task(job_id=job_id,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
            current_frame=chunk_start,
            status='ready',
            priority=50)
        db.session.add(task)
        db.session.commit()

    @staticmethod
    def create_tasks(job):
        job_frames_count = job.frame_end - job.frame_start + 1
        job_chunks_remainder = job_frames_count % job.chunk_size
        job_chunks_division = job_frames_count / job.chunk_size

        if job_chunks_remainder == 0:
            logging.debug('We have exact chunks')

            total_chunks = job_chunks_division
            chunk_start = job.frame_start
            chunk_end = job.frame_start + job.chunk_size - 1

            for chunk in range(total_chunks):
                logging.debug('Making chunk for job {0}'.format(job.id))

                TaskApi.create_task(job.id, chunk_start, chunk_end)

                chunk_start = chunk_end + 1
                chunk_end = chunk_start + job.chunk_size - 1

        elif job_chunks_remainder == job.chunk_size:
            logging.debug('We have only 1 chunk')

            TaskApi.create_task(job.id, job.frame_start, job.frame_end)

        #elif job_chunks_remainder > 0 and \
        #     job_chunks_remainder < job.chunk_size:
        else:
            logging.debug('job_chunks_remainder : {0}'.format(job_chunks_remainder))
            logging.debug('job_frames_count     : {0}'.format(job_frames_count))
            logging.debug('job_chunks_division  : {0}'.format(job_chunks_division))

            total_chunks = job_chunks_division + 1
            chunk_start = job.frame_start
            chunk_end = job.frame_start + job.chunk_size - 1

            for chunk in range(total_chunks - 1):
                logging.debug('Making chunk for job {0}'.format(job.id))

                TaskApi.create_task(job.id, chunk_start, chunk_end)

                chunk_start = chunk_end + 1
                chunk_end = chunk_start + job.chunk_size - 1

            chunk_end = chunk_start + job_chunks_remainder - 1
            TaskApi.create_task(job.id, chunk_start, chunk_end)

    @staticmethod
    def start_task(manager, task):
        """Execute a single task
        We pass manager and task as objects (and at the moment we use a bad
        way to get the additional job information - should be done with join)
        """

        job = Job.query.filter_by(id = task.job_id).first()
        project = Project.query.filter_by(id = job.project_id).first()

        filepath = job.filepath

        # NOTE: probably file_path_linux win and osx should only contain a hashed
        # version of the file name. The full path should be determined by the
        # manager itself. Right now we are assuming that the manager has access
        # to the server storage, which will often not be the case.

        # Also we should consider what to do when sending data over from the server
        # to the wokers.

        params = {'task_id': task.id,
                  'file_path_linux': os.path.join(project.path_linux, filepath),
                  'file_path_win': os.path.join(project.path_win, filepath),
                  'file_path_osx': os.path.join(project.path_osx, filepath),
                  'render_settings': job.render_settings,
                  'start': task.current_frame,
                  'end': task.chunk_end,
                  'output_path_linux': os.path.join(project.render_path_linux, str(task.job_id), '#####'),
                  'output_path_win': os.path.join(project.render_path_win, str(task.job_id), '#####'),
                  'output_path_osx': os.path.join(project.render_path_osx, str(task.job_id), '#####'),
                  'priority' : job.priority,
                  'format': job.format}

        Thread(target=http_rest_request, args=[manager.host, '/tasks', 'post', params]).start()
        task.status = 'running'
        task.manager_id = manager.id
        db.session.add(task)
        db.session.commit()
        # TODO  get a reply from the worker (running, error, etc)

        #task.status = 'running'
        #db.session.add(task)

        #job.current_frame = task.chunk_end
        #db.session.add(job)
        #db.session.commit()

    @staticmethod
    def dispatch_tasks():
        """
        We want to assign a task according to its priority and its assignability
        to the less requested available compatible limited manager. If it does not exist,
        we assign it to the unlimited compatible manager. Otherwise, keep the task and wait
        to the next call to dispatch_tasks


        The task dispaching algorithm works as follows:

        - collect all asked managers
            - detect managers with non virtual workers
        - check if we are dispatching the tasks of a specific job
            - sort tasks in order by priority and assignability to compatible managers
            - assign each task to a compatible manager
        - otherwise
            - assign each task to a compatible manager


        How to assign a task to a manager:

        - collect compatible and available managers and sort them by request
        - if manager's list is not empty
            - assign task to first manager of the list
        - else
            - assign task to compatible unlimited manager
            - if no compatible manager is unlimited, do not assign task (it will wait the next call of dispatch_tasks)
        """
        logging.info('Dispatch tasks')

        tasks = None

        managers = db.session.query(Manager, func.count(JobManagers.manager_id))\
                .join(JobManagers, Manager.id == JobManagers.manager_id)\
                .filter(Manager.has_virtual_workers == 0)\
                .group_by(Manager)\
                .all()

        #Sort task by priority and then by amount of possible manager
        tasks = db.session.query(Task, func.count(JobManagers.manager_id).label('mgr'))\
                    .join(JobManagers, Task.job_id == JobManagers.job_id)\
                    .filter(Task.status == 'ready')\
                    .group_by(Task)\
                    .order_by(Task.priority, 'mgr')\
                    .all()

        for t in tasks:

            job = Job.query.filter_by(id=t[0].job_id).first()
            if not job.status in ['running', 'ready']:
                continue

            rela = db.session.query(JobManagers.manager_id)\
                .filter(JobManagers.job_id == t[0].job_id)\
                .all()

            # Get only accepted available managers
            managers_available = filter(lambda m : m[0].is_available() and (m[0].id,) in rela, managers)

            #Sort managers_available by asking
            managers_available.sort(key=lambda m : m[1])

            if not managers_available:
                print ('No Managers available')
                #Get the first unlimited manager available
                manager_unlimited = Manager.query\
                    .join(JobManagers, Manager.id == JobManagers.manager_id)\
                    .filter(JobManagers.job_id == t[0].job_id)\
                    .filter(Manager.has_virtual_workers == 1)\
                    .first()

                if manager_unlimited:
                    TaskApi.start_task(manager_unlimited, t[0])

            else:
                print ('Managers available')
                TaskApi.start_task(managers_available[0][0], t[0])

    @staticmethod
    def delete_task(task_id):
        # At the moment this function is not used anywhere
        try:
            task = Tasks.query.get(task_id)
        except Exception, e:
            print(e)
            return 'error'
        task.delete_instance()
        print('Deleted task', task_id)

    @staticmethod
    def delete_tasks(job_id):
        tasks = Task.query.filter_by(job_id=job_id)
        for t in tasks:
            # FIXME find sqlalchemy query to avoid this
            if t.status not in ['finished', 'failed', 'aborted', 'ready']:
                manager = Manager.query.get(t.manager_id)
                delete_task = http_rest_request(manager.host, '/tasks/' + str(t.id), 'delete')
                job = Job.query.get(t.job_id)
                if job.current_frame < delete_task['frame_current']:
                    job.current_frame = delete_task['frame_current']
                    db.session.add(job)
                    db.session.commit()
            db.session.delete(t)
            db.session.commit()
        logging.info("All tasks deleted for job {0}".format(job_id))

    @staticmethod
    def stop_task(task_id):
        """Stop a single task
        """
        print ('Stoping task %s' % task_id)
        task = Task.query.get(task_id)
        task.status = 'ready'
        manager = Manager.query.filter_by(id = task.manager_id).first()
        try:
            delete_task = http_rest_request(manager.host, '/tasks/' + str(task.id), 'delete')
        except:
            return
            pass
        task.current_frame = delete_task['frame_current']
        task.status = delete_task['status']
        db.session.add(task)
        db.session.commit()
        print "Task %d stopped" % task_id

    @staticmethod
    def stop_tasks(job_id):
        """We stop all the tasks for a specific job
        """
        tasks = Task.query.\
            filter_by(job_id = job_id).\
            filter_by(status = 'running').\
            all()

        print tasks
        for t in tasks:
            print t
        map(lambda t : TaskApi.stop_task(t.id), tasks)
        #TaskApi.delete_tasks(job_id)

    def get(self):
        from decimal import Decimal
        tasks = {}
        percentage_done = 0
        for task in Task.query.all():

            frame_count = task.chunk_end - task.chunk_start + 1
            current_frame = task.current_frame - task.chunk_start + 1
            percentage_done = Decimal(current_frame) / Decimal(frame_count) * Decimal(100)
            percentage_done = round(percentage_done, 1)
            tasks[task.id] = {"job_id": task.job_id,
                            "chunk_start": task.chunk_start,
                            "chunk_end": task.chunk_end,
                            "current_frame": task.current_frame,
                            "status": task.status,
                            "percentage_done": percentage_done,
                            "priority": task.priority}
        return jsonify(tasks)

    @staticmethod
    def generate_thumbnails(job, start, end):
        # FIXME problem with PIL (string index out of range)
        #thumb_dir = RENDER_PATH + "/" + str(job.id)
        project = Project.query.get(job.project_id)
        thumbnail_dir = os.path.join(project.render_path_server, str(job.id), 'thumbnails')
        if not os.path.exists(thumbnail_dir):
            print '[Debug] ' + os.path.abspath(thumbnail_dir) + " does not exist"
            os.makedirs(thumbnail_dir)
        for i in range(start, end + 1):
            # TODO make generic extension
            #img_name = ("0" if i < 10 else "") + str(i) + get_file_ext(job.format)
            img_name = '{0:05d}'.format(i) + get_file_ext(job.format)
            #file_path = thumb_dir + "/" + str(i) + '.thumb'
            file_path = os.path.join(thumbnail_dir, '{0:05d}'.format(i), '.thumb')
            # We can't generate thumbnail from multilayer with pillow
            if job.format != "MULTILAYER":
                if os.path.exists(file_path):
                    os.remove(file_path)
                frame = os.path.abspath(
                    os.path.join(project.render_path_server, str(job.id), img_name))
                img = Image.open(frame)
                img.thumbnail((150, 150), Image.ANTIALIAS)
                thumbnail_path = os.path.join(thumbnail_dir, '{0:05d}'.format(i) + '.thumb')
                img.save(thumbnail_path, job.format)

    def post(self):
        args = parser.parse_args()
        task_id = args['id']
        status = args['status'].lower()
        if status in ['finished', 'failed']:
            task = Task.query.get(task_id)
            # A non running task cannot be failed or finished
            if task is None or task.status != 'running':
                return '', 204
            job = Job.query.get(task.job_id)
            task.status = status
            db.session.add(task)

            manager = Manager.query.get(task.manager_id)

            if status == 'finished':
                #self.generate_thumbnails(job, task.chunk_start, task.chunk_end)
                logging.info('Task %s finished' % task_id)
            else:
                logging.info('[Info] Task %s failed' % task_id)

            # Check if all tasks have been completed
            if all((lambda t : t.status in ['finished', 'failed'])(t) for t in Task.query.filter_by(job_id=job.id).all()):
                failed_tasks = Task.query.filter_by(job_id=job.id, status='failed').count()
                print ('[Debug] %d tasks failed before') % failed_tasks
                if failed_tasks > 0 or status == 'failed':
                    job.status = 'failed'
                else:
                    job.status = 'completed'
                # this can be added when we update the job for every
                # frame rendered
                # if task.current_frame == job.frame_end:
                #     job.status = 'finished'
                db.session.add(job)
            if task.chunk_end > job.current_frame:
                job.current_frame = task.chunk_end
                db.session.add(job)

            db.session.commit()

        TaskApi.dispatch_tasks()

        return '', 204
