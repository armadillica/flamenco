import logging
from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask.ext.restful import marshal_with
from flask.ext.restful import fields

from application import db
from application import app
from application.utils import list_integers_string

from flask import jsonify
from application import RENDER_PATH
from model import Job
from shutil import rmtree
import os
from os import listdir
from os.path import join
from os.path import exists

from functools import partial

from application.modules.tasks import TaskApi
from application.modules.tasks.model import Task
from application.modules.settings.model import Setting
from application.modules.projects.model import Project

id_list = reqparse.RequestParser()
id_list.add_argument('id', type=str)

status_parser = id_list.copy()
status_parser.add_argument('status', type=str)

job_parser = reqparse.RequestParser()
job_parser.add_argument('project_id', type=int)
job_parser.add_argument('frame_start', type=int)
job_parser.add_argument('frame_end', type=int)
job_parser.add_argument('chunk_size', type=int)
job_parser.add_argument('current_frame', type=int)
job_parser.add_argument('filepath', type=str)
job_parser.add_argument('job_name', type=str)
job_parser.add_argument('render_settings', type=str)
job_parser.add_argument('format', type=str)
job_parser.add_argument('status', type=str)
job_parser.add_argument('priority', type=int)

command_parser = reqparse.RequestParser()
command_parser.add_argument('command', type=str)


job_fields = {
    'id' : fields.Integer,
    'project_id' : fields.Integer,
    'frame_start' : fields.Integer,
    'frame_end' : fields.Integer,
    'chunk_size' : fields.Integer,
    'current_frame' : fields.Integer,
    'filepath' : fields.String,
    'job_name' : fields.String,
    'render_settings' : fields.String,
    'format' : fields.String,
    'status' : fields.String,
    'priority' : fields.String
}

class JobListApi(Resource):
    def get(self):
        jobs = {}
        for job in Job.query.all():
            percentage_done = 0
            frame_count = job.frame_end - job.frame_start + 1
            percentage_done = round(float(job.current_frame) / float(frame_count) * 100.0,
                                    1)

            jobs[job.id] = {"job_name" : job.name,
                            "frame_start" : job.frame_start,
                            "frame_end" : job.frame_end,
                            "current_frame" : job.current_frame,
                            "status" : job.status,
                            "percentage_done" : percentage_done,
                            "render_settings" : job.render_settings,
                            "format" : job.format }

        return jsonify(jobs)

    def start(self, job_id):
        job = Job.query.get(job_id)
        if job:
            if job.status != 'running':
                job.status = 'running'
                db.session.add(job)
                db.session.commit()
                print ('[debug] Dispatching tasks')
            TaskApi.dispatch_tasks()
        else:
            print('[error] Job %d not found' % job_id)
            raise KeyError

    def stop(self, job_id):
        print '[info] Working on job', job_id
        # first we delete the associated jobs (no foreign keys)
        job = Job.query.get(job_id)
        if job:
            if job.status != 'stopped':
                TaskApi.stop_tasks(job.id)
                job.status = 'stopped'
                db.session.add(job)
                db.session.commit()
        else:
            print('[error] Job %d not found' % job_id)
            raise KeyError

    def reset(self, job_id):
        job = Job.query.get(job_id)
        if job:
            if job.status == 'running':
                print'Job %d is running' % job_id
                raise KeyError
            else:
                job.current_frame = job.frame_start
                job.status = 'ready'
                db.session.add(job)
                db.session.commit()

                TaskApi.delete_tasks(job.id)
                TaskApi.create_tasks(job)

                path = RENDER_PATH + "/" + str(job.id)
                if os.path.exists(path):
                    rmtree(path)
        else:
            print('[error] Job %d not found' % job_id)
            raise KeyError

    def respawn(self, job_id):
        job = Job.query.get(job_id)
        if job:
            if job.status == 'running':
                self.stop(job_id)

            tasks = Task.query.filter_by(job_id=job_id)
            best_managers = filter(lambda m : m.total_workers == -1, app.config['MANAGERS'])

            if best_managers:
                fun = partial(TaskApi.start_task, best_managers[0])
                map(fun, tasks)
            else:
                TaskApi.dispatch_tasks(job_id)
        else:
            logging.error('Job %d not found' % job_id)
            raise KeyError


    def put(self):
        args = status_parser.parse_args()
        fun = None
        if args['status'] == "start":
            fun = self.start
        elif args['status'] == "stop":
            fun = self.stop
        elif args['status'] == "reset":
            fun = self.reset
        elif args['status'] == "respawn":
            fun = self.respawn
        else:
            print "command not found"
            return args, 400

        try:
            map(fun, list_integers_string(args['id']))
        except KeyError:
            return args, 404

        args['status'] = 'running'
        return args, 200

    @marshal_with(job_fields)
    def post(self):
        args = job_parser.parse_args()
        job = Job(
           project_id=args['project_id'],
           frame_start=args['frame_start'],
           frame_end=args['frame_end'],
           chunk_size=args['chunk_size'],
           current_frame=args['current_frame'],
           filepath=args['filepath'],
           name=args['job_name'],
           render_settings=args['render_settings'],
           format=args['format'],
           status=args['status'],
           priority=args['priority'])

        db.session.add(job)
        db.session.commit()

        logging.info('Parsing job to create tasks')
        TaskApi.create_tasks(job)
        logging.info('Refresh list of available workers')
        TaskApi.dispatch_tasks(job.id)
        return job, 201


class JobApi(Resource):
    @marshal_with(job_fields)
    def get(self, job_id):
        job = Job.query.get_or_404(job_id)
        return job

    @marshal_with(job_fields)
    def put(self, job_id):
        job = Job.query.get_or_404(job_id)
        args = job_parser.parse_args()
        commands = command_parser.parse_args()
        # Here we can handle direct commands for a job, that do not fit the
        # restful principle. For example restart, stop, start, etc.
        if commands['command']:
            if commands['command'] == 'start':
                self.start(job_id)
                return job
            elif commands['command'] == 'stop':
                self.stop(job_id)
                return job # stop job
            elif commands['command'] == 'reset':
                return job # reset job
            else:
                response = jsonify({
                    'code' : 400,
                    'message': 'Unknown command. Try "start", "stop" or "reset"'})
                response.status_code = 400
                return response
        else:
            # We edit properties of the job, such as the title, the frame
            # range and so on
            logging.info('Updating job: {0} - {1}'.format(job.id, job.name))
            for arg in args:
                if args[arg]: setattr(job, arg, args[arg])
            db.session.commit()

            return job

    @staticmethod
    def delete(job_id):
        """Depending on the database, we migh want to specify or not CASCADE
        directives for attached tasks. In order to delete a job, it should
        be not rendering or processing.
        """
        job = Job.query.get_or_404(job_id)
        db.session.delete(job)

        return '', 204

    @staticmethod
    def start(job_id):
        job = Job.query.get(job_id)
        if job.status != 'running':
            job.status = 'running'
            db.session.add(job)
            db.session.commit()
            logging.info('Dispatching tasks')
        else:
            pass
            # TODO (fsiddi): proper error message if jobs is already running
        TaskApi.dispatch_tasks()

    @staticmethod
    def stop(job_id):
        logging.info('Stopping job {0}'.format(job_id))
        job = Job.query.get(job_id)
        if job.status != 'stopped':
            TaskApi.stop_tasks(job.id)
            job.status = 'stopped'
            db.session.add(job)
            db.session.commit()
        else:
            pass
            # TODO (fsiddi): proper error message if jobs is already stopped

    @staticmethod
    def reset(job_id):
        job = Job.query.get(job_id)
        if job.status == 'running':
            logging.error('Job {0} is running'.format(job_id))
            response = jsonify({
                'code' : 400,
                'message': 'This job is running, stop it first.'})
            response.status_code = 400
            return response
        else:
            job.current_frame = job.frame_start
            job.status = 'ready'
            db.session.add(job)
            db.session.commit()

            TaskApi.delete_tasks(job.id)
            TaskApi.create_tasks(job)

            path = RENDER_PATH + "/" + str(job.id)
            if os.path.exists(path):
                rmtree(path)
            logging.info('Job {0} reset end ready'.format(job_id))


class JobDeleteApi(Resource):
    def post(self):
        args = id_list.parse_args()
        print Job.query.all()
        print args['id']
        int_list = list_integers_string(args['id'])
        for j in int_list:
            TaskApi.delete_tasks(j)
            job = Job.query.get(j)
            if job:
                path = join(RENDER_PATH, str(j))
                if exists(path):
                    rmtree(path)

                db.session.delete(job)
                db.session.commit()
                print "[info] Deleted job %d" % j
            else:
                print "[error] Job %d not found" % j
                return '', 404

        return '', 204
