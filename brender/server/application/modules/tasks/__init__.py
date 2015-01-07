import os
import logging

from flask.ext.restful import Resource
from flask.ext.restful import reqparse

from flask import abort
from flask import jsonify
from flask import render_template
from flask import request

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

from threading import Thread

parser = reqparse.RequestParser()
parser.add_argument('id', type=int)
parser.add_argument('status', type=str)


class TaskApi(Resource):
    @staticmethod
    def create_task(job_id, chunk_start, chunk_end):
        # TODO attribution of the best manager
        task = Task(job_id=job_id,
            manager_id=1,
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

                create_task(job.id, chunk_start, chunk_end)

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

        http_rest_request(manager.host, '/tasks', 'post', params)
        task.status = 'running'
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
        logging.info('dispatch tasks')
        # TODO Use databse
        #managers = Manager.query.\
        #    all()
        managers = iter(sorted(app.config['MANAGERS'], key=lambda m : m.total_workers, reverse=True))
        tasks = None
        if job_id is None:
            tasks = Task.query.filter_by(status='ready').order_by(Task.priority.desc())
        else:
            tasks = Task.query.filter_by(job_id=job_id).order_by(Task.priority.desc())

        # We get the available managers
        try:
            m = managers.next()
            while not m.is_available():
                m = managers.next()

            for task in tasks:
                TaskApi.start_task(m, task)
                m.running_tasks = m.running_tasks + 1

                while not m.is_available():
                    m = managers.next()
        except StopIteration:
            pass

        #for manager in managers:
        #    # pick the task with the highest priority (it means the lowest number)

        #    task = Task.query.\
        #        filter_by(status='ready').\
        #        order_by(Task.priority.desc()).\
        #        first()

        #    if task:
        #        TaskApi.start_task(manager, task)
            #else:
            #    print '[error] Task does not exist'

            """Legacy code
            task = None # will figure out another way
            try:
                task = Tasks.select().where(
                    Tasks.status == 'ready'
                ).order_by(Tasks.priority.desc()).limit(1).get()

                task.status = 'running'
                task.save()
            except Tasks.DoesNotExist:
                print '[error] Task does not exist'
            if task:
                start_task(worker, task)
            """

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
            #TODO use database
            #manager = Manager.query.get(t.manager_id)
            manager = filter(lambda m : m.id == t.manager_id, app.config['MANAGERS'])[0]
            # FIXME find sqlalchemy query to avoid this
            if t.status not in ['finished', 'failed', 'aborted']:
                delete_task = http_rest_request(manager.host, '/tasks/' + str(t.id), 'delete')
                mananger.running_tasks = manager.running_tasks - 1
                job = Job.query.get(t.job_id)
                if job.current_frame < delete_task['frame_current']:
                    job.current_frame = delete_task['frame_current']
                    db.session.add(job)
                    db.session.commit()
            db.session.delete(t)
            db.session.commit()
        print('All tasks deleted for job', job_id)

    @staticmethod
    def stop_task(task_id):
        """Stop a single task
        """
        task = Task.query.get(task_id)
        task.status = 'ready'
        #TODO use database
        #manager = Manager.query.get(task.manager_id)
        manager = filter(lambda m : m.id == task.manager_id, app.config['MANAGERS'])[0]
        delete_task = http_rest_request(manager.host, '/tasks/' + str(task.id), 'delete')
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
            file_path = os.path.join(thumbnail_dir, str(i), '.thumb')
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

            # TODO Use database
            manager = filter(lambda m : m.id == task.manager_id, app.config['MANAGERS'])[0]
            manager.running_tasks = manager.running_tasks - 1

            if status == 'finished':
                self.generate_thumbnails(job, task.chunk_start, task.chunk_end)
            else:
                print ('[Info] Task %s failed') % task_id

            if task.chunk_end == job.frame_end:
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

        Thread(target=TaskApi.dispatch_tasks).start()

        return '', 204
