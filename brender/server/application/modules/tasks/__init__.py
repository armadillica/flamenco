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
from application import db, RENDER_PATH
from PIL import Image
from platform import system

from application.modules.tasks.model import Task
from application.modules.workers.model import Worker
from application.modules.jobs.model import Job
from application.modules.projects.model import Project
from application.modules.settings.model import Setting

parser = reqparse.RequestParser()
parser.add_argument('id', type=int)
parser.add_argument('status', type=str)


class TaskApi(Resource):
    @staticmethod
    def create_task(job_id, chunk_start, chunk_end):
        task = Task(job_id=job_id,
            worker_id=12,
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
    def start_task(worker, task):
        """Execute a single task
        We pass worker and task as objects (and at the moment we use a bad
        way to get the additional job information - should be done with join)
        """

        job = Job.query.filter_by(id = task.job_id).first()
        project = Project.query.filter_by(id = job.project_id).first()

        filepath = job.filepath

        if 'Darwin' in worker.system:
            setting_blender_path = Setting.query.filter_by(name='blender_path_osx').first()
            setting_render_settings = Setting.query.filter_by(name='render_settings_path_osx').first()
            filepath = os.path.join(project.path_osx, job.filepath)
        elif 'Windows' in worker.system:
            setting_blender_path = Setting.query.filter_by(name='blender_path_win').first()
            setting_render_settings = Setting.query.filter_by(name='render_settings_path_win').first()
            filepath = os.path.join(project.path_win, job.filepath)
        else:
            setting_blender_path = Setting.query.filter_by(name='blender_path_linux').first()
            setting_render_settings = Setting.query.filter_by(name='render_settings_path_linux').first()
            filepath = os.path.join(project.path_linux, job.filepath)

        if setting_blender_path is None:
            print '[Debug] blender path is not set'

        blender_path = setting_blender_path.value

        if setting_render_settings is None:
            print '[Debug] render settings is not set'

        render_settings = os.path.join(
            setting_render_settings.value ,
            job.render_settings)

        worker_ip_address = worker.ip_address

        """
        Additional params for future reference

        task_parameters = {'pre-run': 'svn up or other things',
                          'command': 'blender_path -b ' +
                                     '/filepath.blend -o /render_out -a',
                          'post-frame': 'post frame',
                          'post-run': 'clear variables, empty /tmp'}
        """

        params = {'task_id': task.id,
                  'file_path': filepath,
                  'blender_path': blender_path,
                  'render_settings': render_settings,
                  'start': task.chunk_start,
                  'end': task.chunk_end,
                  'output': "//" + RENDER_PATH + "/" + str(task.job_id)  + "/##",
                  'format': job.format}

        http_request(worker_ip_address, '/execute_task', params)
        #  get a reply from the worker (running, error, etc)

        task.status = 'running'
        db.session.add(task)

        job.current_frame = task.chunk_end
        db.session.add(job)
        db.session.commit()

    @staticmethod
    def dispatch_tasks(job_id=None):
        workers = Worker.query.\
            filter_by(status='enabled').\
            filter_by(connection='online').\
            all()
        for worker in workers:
            # pick the task with the highest priority (it means the lowest number)

            task = Task.query.\
                filter_by(status='ready').\
                order_by(Task.priority.desc()).\
                first()

            if task:
                task.status = 'running'
                db.session.add(task)
                db.session.commit()
                TaskApi.start_task(worker, task)
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
        tasks = Task.query.filter_by(job_id=job_id).delete()
        print('All tasks deleted for job', job_id)

    @staticmethod
    def stop_task(task_id):
        """Stop a single task
        """
        task = Task.query.get(task_id)
        task.status = 'ready'
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

        map(lambda t : TaskApi.stop_task(t.id), tasks)

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
    def generate_thumbnails(job, begin, end):
        thumb_dir = RENDER_PATH + "/" + str(job.id)
        project = Project.query.get(job.project_id)
        if not os.path.exists(thumb_dir):
            print '[Debug] ' + os.path.abspath(thumb_dir) + " does not exist"
            os.makedirs(thumb_dir)
        for i in range(begin, end + 1):
            # TODO make generic extension
            img_name = ("0" if i < 10 else "") + str(i) + get_file_ext(job.format)
            file_path = thumb_dir + "/" + str(i) + '.thumb'
            # We can't generate thumbnail from multilayer with pillow
            if job.format != "MULTILAYER":
                if os.path.exists(file_path):
                    os.remove(file_path)
                img_path = os.path.abspath(project.path_server + "/" + RENDER_PATH \
                        + "/" + str(job.id) + "/" + img_name)
                img = Image.open(img_path)
                img.thumbnail((150, 150), Image.ANTIALIAS)
                thumb_path = thumb_dir + "/" + str(i) + '.thumb'
                img.save(thumb_path, job.format)

    def post(self):
        args = parser.parse_args()
        task_id = args['id']
        status = args['status'].lower()
        if status in ['finished', 'failed']:
            task = Task.query.get(task_id)
            job = Job.query.get(task.job_id)
            task.status = status
            db.session.add(task)

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
            db.session.commit()

        TaskApi.dispatch_tasks()

        return '', 204
