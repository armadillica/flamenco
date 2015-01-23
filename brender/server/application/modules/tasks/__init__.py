import os
import logging

from flask.ext.restful import Resource
from flask.ext.restful import reqparse

from flask import abort
from flask import jsonify
from flask import render_template
from flask import request

from sqlalchemy import func

# TODO(sergey): Generally not a good idea to import *
from application.utils import *
from application import app
from application import db
from PIL import Image
from platform import system

from application import app
from application.modules.tasks.model import Task
from application.modules.managers.model import Manager
from application.modules.jobs.model import Job
from application.modules.projects.model import Project
from application.modules.settings.model import Setting
from application.modules.jobs.model import JobManagers

from threading import Thread

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

        #if 'Darwin' in worker.system:
        #    setting_blender_path = Setting.query.filter_by(name='blender_path_osx').first()
        #    setting_render_settings = Setting.query.filter_by(name='render_settings_path_osx').first()
        #    filepath = os.path.join(project.path_osx, job.filepath)
        #elif 'Windows' in worker.system:
        #    setting_blender_path = Setting.query.filter_by(name='blender_path_win').first()
        #    setting_render_settings = Setting.query.filter_by(name='render_settings_path_win').first()
        #    filepath = os.path.join(project.path_win, job.filepath)
        #else:
        #    setting_blender_path = Setting.query.filter_by(name='blender_path_linux').first()
        #    setting_render_settings = Setting.query.filter_by(name='render_settings_path_linux').first()
        #    filepath = os.path.join(project.path_linux, job.filepath)

        #if setting_blender_path is None:
        #    print '[Debug] blender path is not set'

        #blender_path = setting_blender_path.value

        #if setting_render_settings is None:
        #    print '[Debug] render settings is not set'

        #render_settings = os.path.join(
        #    setting_render_settings.value,
        #    job.render_settings)

        """
        Additional params for future reference

        task_parameters = {'pre-run': 'svn up or other things',
                          'command': 'blender_path -b ' +
                                     '/filepath.blend -o /render_out -a',
                          'post-frame': 'post frame',
                          'post-run': 'clear variables, empty /tmp'}
        """

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
    def dispatch_tasks(job_id=None):
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

        if job_id is None:
            #Sort task by priority and then by amount of possible manager
            tasks = db.session.query(Task, func.count(JobManagers.manager_id).label('mgr'))\
                        .join(JobManagers, Task.job_id == JobManagers.job_id)\
                        .filter(Task.status == 'ready')\
                        .group_by(Task)\
                        .order_by(Task.priority, 'mgr')\
                        .all()

            print tasks
            for t in tasks:
                rela = db.session.query(JobManagers.manager_id)\
                    .filter(JobManagers.job_id == t[0].job_id)\
                    .all()

                # Get only accepted available managers
                managers_available = filter(lambda m : m[0].is_available() and (m[0].id,) in rela, managers)

                #Sort managers_available by asking
                managers_available.sort(key=lambda m : m[1])

                if not managers_available:
                    #Get the first unlimited manager available
                    manager_unlimited = Manager.query\
                        .join(JobManagers, Manager.id == JobManagers.manager_id)\
                        .filter(JobManagers.job_id == t[0].job_id)\
                        .filter(Manager.has_virtual_workers == 1)\
                        .first()

                    if manager_unlimited:
                        TaskApi.start_task(manager_unlimited, t[0])
                        manager_unlimited.running_tasks += 1
                        db.session.commit()

                else:
                    TaskApi.start_task(managers_available[0][0], t[0])
                    managers_available[0][0].running_tasks = managers_available[0][0].running_tasks + 1
                    db.session.add(managers_available[0][0])
                    db.session.commit()

        else:
            tasks = Task.query.filter_by(job_id=job_id,status='ready').all()
            print tasks
            rela = db.session.query(JobManagers.manager_id)\
                .filter(JobManagers.job_id == job_id)\
                .all()

            for t in tasks:
                # Get only accepted available managers_available
                managers_available = filter(lambda m : m[0].is_available() and (m[0].id,) in rela, managers)
                for m in managers_available:
                    print m[0].is_available()
                    print m[0].total_workers - m[0].running_tasks
                #Sort managers_available by asking
                managers_available.sort(key=lambda m : m[1])
                if not managers_available:
                    #Get unlimited associated managers_available
                    logging.info('No limited manager available')
                    #managers_unlimited = filter(lambda m : m.has_virtual_workers == 1 and (m.id,) in rela, Manager.query.all())
                    manager_unlimited = Manager.query.join(JobManagers, Manager.id == JobManagers.manager_id)\
                            .filter(JobManagers.job_id == job_id)\
                            .filter(Manager.has_virtual_workers == 1)\
                            .first()
                    if manager_unlimited:
                        logging.info('Send to unlimited manager')
                        TaskApi.start_task(manager_unlimited, t)
                        manager_unlimited.running_tasks += 1
                        db.session.commit()

                else:
                    logging.info('Send to limited manager')
                    TaskApi.start_task(managers_available[0][0], t)
                    managers_available[0][0].running_tasks = managers_available[0][0].running_tasks + 1
                    db.session.add(managers_available[0][0])
                    db.session.commit()

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
                if manager.total_workers is not None:
                    manager.running_tasks = manager.running_tasks - 1
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
        task = Task.query.get(task_id)
        task.status = 'ready'
        #TODO use database
        #manager = Manager.query.get(task.manager_id)
        manager = filter(lambda m : m.id == task.manager_id, Manager.query.all())[0]
        delete_task = http_rest_request(manager.host, '/tasks/' + str(task.id), 'delete')
        if manager.total_workers is not None:
            manager.running_tasks = manager.running_tasks - 1
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
            manager.running_tasks = manager.running_tasks - 1
            db.session.add(manager)

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
                db.session.query(JobManagers).filter(JobManagers.job_id == job.id).delete()
            if task.chunk_end > job.current_frame:
                job.current_frame = task.chunk_end
                db.session.add(job)

            db.session.commit()

        TaskApi.dispatch_tasks()

        return '', 204
