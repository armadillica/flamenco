from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask.ext.restful import marshal_with
from flask.ext.restful import fields

from application import db
from application.utils import list_integers_string

from flask import jsonify
from application import RENDER_PATH
from model import Job
from shutil import rmtree
import os
from os import listdir
from os.path import join
from os.path import exists

from application.modules.tasks import TaskApi
from application.modules.settings.model import Setting
from application.modules.projects.model import Project

id_list = reqparse.RequestParser()
id_list.add_argument('id', type=str)

status_parser = id_list.copy()
status_parser.add_argument('status', type=str)

parser = reqparse.RequestParser()
parser.add_argument('project_id', type=int)
parser.add_argument('frame_start', type=int)
parser.add_argument('frame_end', type=int)
parser.add_argument('chunk_size', type=int)
parser.add_argument('current_frame', type=int)
parser.add_argument('filepath', type=str)
parser.add_argument('name', type=str)
parser.add_argument('render_settings', type=str)
parser.add_argument('format', type=str)
parser.add_argument('status', type=str)
parser.add_argument('priority', type=int)

job_fields = {
    'project_id' : fields.Integer,
    'frame_start' : fields.Integer,
    'frame_end' : fields.Integer,
    'chunk_size' : fields.Integer,
    'current_frame' : fields.Integer,
    'filepath' : fields.String,
    'name' : fields.String,
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

            jobs[job.id] = {
                            "job_name" : job.name,
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

    def put(self):
        args = status_parser.parse_args()
        fun = None
        if args['status'] == "start":
            fun = self.start
        elif args['status'] == "stop":
            fun = self.stop
        elif args['status'] == "reset":
            fun = self.reset
        else:
            return args, 400

        try:
            map(fun, args['id'])
        except KeyError:
            return args, 404

        args['status'] = 'running'
        return args, 200

    @marshal_with(job_fields)
    def post(self):
        args = parser.parse_args()
        job = Job(
           project_id=args['project_id'],
           frame_start=args['frame_start'],
           frame_end=args['frame_end'],
           chunk_size=args['chunk_size'],
           current_frame=args['current_frame'],
           filepath=args['filepath'],
           name=args['name'],
           render_settings=args['render_settings'],
           format=args['format'],
           status=args['status'],
           priority=args['priority'])

        db.session.add(job)
        db.session.commit()

        print 'parsing job to create tasks'

        TaskApi.create_tasks(job)

        print 'refresh list of available workers'

        TaskApi.dispatch_tasks(job.id)

        return job, 201


class JobApi(Resource):
    @marshal_with(job_fields)
    def get(self, job_id):
       job = Job.query.get_or_404(job_id)
       return job


class JobDeleteApi(Resource):
    def post(self):
        args = id_list.parse_args()
        print args['id']
        int_list = list_integers_string(args['id'])
        for j in int_list:
            print 'working on %d - %s' % (j, str(type(j)))
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


class JobBrowsing(Resource):
    @staticmethod
    def browse(path):
        """We browse the production folder on the server.
        The path value gets appended to the active_project path value. The result is returned
        in JSON format.
        """

        active_project = Setting.query.filter_by(name = 'active_project').first()
        active_project = Project.query.get(active_project.value)

        # path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        # render_settings_path = os.path.join(path, 'render_settings/')

        absolute_path_root = active_project.path_server
        parent_path = ''

        if path != '':
            absolute_path_root = os.path.join(absolute_path_root, path)
            parent_path = path + "/" + os.pardir

        # print(active_project.path_server)
        # print(listdir(active_project.path_server))

        # items = {}
        items_list = []

        for f in listdir(absolute_path_root):
            relative_path = os.path.join(path, f)
            absolute_path = os.path.join(absolute_path_root, f)

            # we are going to pick up only blend files and folders
            if absolute_path.endswith('blend'):
                # items[f] = relative_path
                items_list.append((f, relative_path, 'blendfile'))
            elif os.path.isdir(absolute_path):
                items_list.append((f, relative_path, 'folder'))

        #return str(onlyfiles)
        project_files = dict(
            project_path_server=active_project.path_server,
            parent_path=parent_path,
            # items=items,
            items_list=items_list)

        return project_files


    def get(self, path):
        return jsonify(self.browse(path))


class JobRootBrowsing(Resource):
    def get(self):
        return jsonify(JobBrowsing.browse(''))
