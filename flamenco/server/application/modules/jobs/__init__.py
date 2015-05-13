import logging
import os
import json
import shutil
import requests
import time
from PIL import Image
from os import listdir
from os.path import join
from os.path import exists
from shutil import rmtree
from functools import partial
from sqlalchemy import or_
from zipfile import ZipFile

from flask import jsonify
from flask import Response
from flask import request
from flask import send_from_directory

from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask.ext.restful import marshal_with
from flask.ext.restful import fields

from werkzeug.datastructures import FileStorage

from application import db
from application import app
from application.utils import list_integers_string

from application.modules.tasks import TaskApi
from application.modules.tasks import TaskListApi
from application.modules.tasks.model import Task
from application.modules.settings.model import Setting
from application.modules.projects.model import Project
from application.modules.jobs.model import Job
from application.modules.jobs.model import JobManagers
from application.modules.managers.model import Manager
from application.modules.log import log_to_database

id_list = reqparse.RequestParser()
id_list.add_argument('id', type=str)

list_command_parser = id_list.copy()
list_command_parser.add_argument('command', type=str)

job_parser = reqparse.RequestParser()
job_parser.add_argument('project_id', type=int)
job_parser.add_argument('name', type=str)
job_parser.add_argument('priority', type=int)
job_parser.add_argument('start_job', type=bool, default=False)
job_parser.add_argument('managers', type=int, action='append')
job_parser.add_argument('type', type=str)
job_parser.add_argument('settings', type=str)
job_parser.add_argument('jobfile', type = FileStorage, location = 'files')

command_parser = reqparse.RequestParser()
command_parser.add_argument('command', type=str)

parser_thumbnail = reqparse.RequestParser()
parser_thumbnail.add_argument("task_id", type=int)


job_fields = {
    'project_id' : fields.Integer,
    'settings' : fields.String,
    'name' : fields.String,
    'type' : fields.String,
    'priority' : fields.Integer,
}

class jobInfo():
    @staticmethod
    def get(job, embed_tasks=False):
        """Global function to get info about one job"""

        # Collect all tasks related to the job
        tasks = Task.query.filter_by(job_id=job.id).all()
        # Query again, but filtering only for finished jobs (refactor this!)
        tasks_completed = Task.query\
            .filter_by(job_id=job.id, status='finished').count()

        # Default completion value
        percentage_done = 0

        # Update percentabe value if the job has at least 1 complete task
        if tasks and tasks_completed:
            percentage_done = round(float(tasks_completed) / float(len(tasks)) * 100.0, 1)

        # Define other default values
        remaining_time = None
        average_time = None
        total_time = 0
        job_time = 0
        finished_time = 0
        finished_tasks = 0
        running_tasks = 0
        frames_rendering = ""
        frame_remaining = None
        activity = ""

        for task in tasks:
            try:
                task_activity = json.loads(task.activity)
            except:
                # If the task status is not in JSON format, or any other error
                task_activity = None

            if task.status == 'finished':
                if task.time_cost:
                    finished_time = finished_time + task.time_cost
                finished_tasks += 1
            if task.status == 'running':
                running_tasks += 1
                if task_activity and task_activity.get('current_frame'):
                    frames_rendering = "{0} {1}".format(
                        frames_rendering, task_activity.get('current_frame'))
                    if task_activity.get('remaining'):
                        frames_rendering = "{0} ({1}sec)".format(
                            frames_rendering, task_activity.get('remaining'))

            if task.time_cost:
                total_time += task.time_cost

        if job.status == 'running':
            if finished_tasks > 0:
                average_time = finished_time / finished_tasks
            if finished_tasks > 0:
                remaining_time = (average_time * len(tasks)) - total_time
            if remaining_time and running_tasks > 0:
                remaining_time = remaining_time / running_tasks
            activity = "Rendering: {0}.".format(frames_rendering)
        elif job.status == 'completed':
            average_time = finished_time / finished_tasks

        if running_tasks > 0:
            job_time = total_time/running_tasks

        if embed_tasks:
            embedded_tasks = TaskListApi.get_tasks_list(tasks)
        else:
            embedded_tasks = None

        # TODO: incorporate this in the original job query
        job_managers = JobManagers.query.filter_by(job_id=job.id).first()

        job_info = {
            "id" : job.id,
            "job_name" : job.name,
            "project_id" : job.project_id,
            "status" : job.status,
            "settings" : json.loads(job.settings),
            "activity" : activity,
            "remaining_time" : remaining_time,
            "average_time" : average_time,
            "total_time" : total_time,
            "job_time" : job_time,
            "type" : job.type,
            "priority" : job.priority,
            "percentage_done" : percentage_done,
            "creation_date" : job.creation_date,
            "tasks" : embedded_tasks,
            "manager": job_managers.manager.name
            }
        return job_info


class JobListApi(Resource):
    def get(self):
        jobs = {}
        for job in Job.query.filter(Job.status != 'archived').all():
            jobs[job.id] = jobInfo.get(job)

        return jsonify(jobs)

    def start(self, job_id):
        job = Job.query.get(job_id)
        if job:
            if job.status not in ['running', 'completed']:
                job.status = 'running'
                db.session.add(job)

                db.session.query(Task).filter(Task.job_id == job_id)\
                        .filter(or_(Task.status == 'aborted',
                                Task.status == 'failed'))\
                        .update({'status' : 'ready'})
                db.session.commit()
        else:
            print('[error] Job %d not found' % job_id)
            raise KeyError

    def stop(self, job_id):
        print '[info] Stopping job', job_id
        # first we delete the associated jobs (no foreign keys)
        job = Job.query.get(job_id)
        if job:
            if job.status not in ['stopped', 'completed', 'failed']:
                job.status = 'stopped'
                db.session.add(job)
                db.session.commit()
                TaskApi.stop_tasks(job.id)
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
                job.status = 'ready'
                db.session.add(job)
                db.session.commit()

                TaskApi.delete_tasks(job.id)
                TaskApi.create_tasks(job)

                path = join(
                    job.project.render_path_server, str(job.id))
                if exists(path):
                    rmtree(path)
        else:
            print('[error] Job %d not found' % job_id)
            raise KeyError

    def respawn(self, job_id):
        job = Job.query.get(job_id)
        if job:
            if job.status == 'running':
                self.stop(job_id)

            tasks = db.session.query(Task).filter(
                Task.job_id == job_id, Task.status.notin_(
                    ['finished','failed'])).all()
            best_managers = db.session.query(Manager).join(
                JobManagers, Manager.id == JobManagers.manager_id)\
                    .filter(JobManagers.job_id == job_id)\
                    .filter(Manager.has_virtual_workers == 1)\
                    .first()

            if best_managers:
                fun = partial(TaskApi.start_task, best_managers)
                map(fun, tasks)
            else:
                map(lambda t : setattr(t, 'status', 'ready'), tasks)
                db.session.commit()
                TaskApi.dispatch_tasks()
        else:
            logging.error('Job %d not found' % job_id)
            raise KeyError

    def put(self):
        """Run a command against a list of jobs.
        """
        args = list_command_parser.parse_args()
        # Parse the string list of job IDs into a real integers list
        args['id'] = list_integers_string(args['id'])
        fun = None
        # Set a status variable, for returning a status to display in the UI
        status = None
        if args['command'] == "start":
            fun = self.start
            status = "running"
        elif args['command'] == "stop":
            fun = self.stop
            status = "stopped"
        elif args['command'] == "reset":
            fun = self.reset
            status = "reset"
        elif args['command'] == "respawn":
            fun = self.respawn
            status = "respawned"
        elif args['command'] == "archive":
            fun = JobApi.archive
            status = "archived"
        else:
            logging.error("command not found")
            return args, 400

        try:
            # Run the right function (according to the command specified) against
            # a list of job IDs
            map(fun, args['id'])
            # Return a dictionary with the IDs list, the command that was run
            # agains them and the status they have after such command has been
            # executed
            return dict(
                id=args['id'], command=args['command'], status=status), 200
        except KeyError:
            return args, 404

        args['status'] = 'running'
        return args, 200

    @marshal_with(job_fields)
    def post(self):
        args = job_parser.parse_args()

        """job_settings = {
            'frame_start' : args['frame_start'],
            'frame_end' : args['frame_end'],
            'chunk_size' : args['chunk_size'],
            'filepath' : args['filepath'],
            'render_settings' : args['render_settings'],
            'format' : args['format'],
            }"""

        status = "stopped"
        if args['start_job']:
            status = 'running'

        job = Job(
           project_id=args['project_id'],
           settings=args['settings'],
           name=args['name'],
           status=status,
           type=args['type'],
           priority=args['priority'])

        db.session.add(job)
        db.session.commit()

        serverstorage = app.config['SERVER_STORAGE']
        projectpath = join(serverstorage, str(job.project_id))

        try:
            os.mkdir(projectpath)
        except:
            pass

        if args['jobfile']:
            jobpath = join(projectpath, str(job.id))
            try:
                os.mkdir(jobpath)
            except:
                pass
            args['jobfile'].save(join(jobpath, 'jobfile_{0}.zip'.format(job.id)))


        allowed_managers = args['managers']
        for m in allowed_managers:
            print "allowed managers: %d" % int(m)
            db.session.add(JobManagers(job_id=job.id, manager_id=int(m)))

        db.session.commit()
        TaskApi.create_tasks(job)
        return job, 201


class JobApi(Resource):
    def get(self, job_id):
        job = Job.query.get(job_id)
        job_info = jobInfo.get(job, embed_tasks=True)
        return jsonify(job_info)

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
            elif commands['command'] == 'archive':
                self.archive(job_id)
                return job # archive job
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
        #TaskApi.dispatch_tasks()

    @staticmethod
    def stop(job_id):
        logging.info('Stopping job {0}'.format(job_id))
        job = Job.query.get(job_id)
        if job.status != 'stopped':
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

            #Security check
            insecure_names=[None, "", "/", "\\", ".", ".."]
            path = join(job.project.render_path_server, str(job.id))
            if job.project.render_path_server not in insecure_names and str(job.id) not in insecure_names:
                if exists(path):
                    rmtree(path)
            logging.info('Job {0} reset end ready'.format(job_id))

    @staticmethod
    def archive(job_id):
        logging.info('Archiving job {0}'.format(job_id))
        job = Job.query.get(job_id)
        if job.status != 'running':
            log = "Status changed from {0} to {1}".format(job.status, 'archived')
            job.status = 'archived'
            db.session.commit()
            log_to_database(job_id, 'job', log)
        else:
            pass


class JobDeleteApi(Resource):
    def post(self):
        args = id_list.parse_args()
        int_list = list_integers_string(args['id'])
        for j in int_list:
            TaskApi.delete_tasks(j)
            job = Job.query.get(j)
            if job:
                #path = join(job.project.render_path_server, str(j))
                #Security check
                #insecure_names=[None, "", "/", "\\", ".", ".."]
                #if job.project.render_path_server not in insecure_names and str(j) not in insecure_names:
                #    if exists(path):
                #        rmtree(path)

                db.session.query(JobManagers)\
                    .filter(JobManagers.job_id == job.id).delete()
                db.session.delete(job)
                db.session.commit()
                logging.info("Deleted job {0}".format(j))
            else:
                logging.error("Job {0} not found".format(j))
                return '', 404

        return '', 204


class JobThumbnailListApi(Resource):
    """Thumbnail list interface for the Server
    """
    def allowed_file(self, filename):
        """Filter extensions acording to THUMBNAIL_EXTENSIONS configuration.
        """
        return '.' in filename and \
               filename.rsplit('.', 1)[1] in app.config['THUMBNAIL_EXTENSIONS']

    def post(self):
        """Accepts a thumbnail file and a task_id and stores it.
        """
        args = parser_thumbnail.parse_args()
        task = Task.query.get(args['task_id'])
        if not task:
            return
        thumbnail_filename = "thumbnail_%s.png" % task.job_id

        file = request.files['file']
        if file and self.allowed_file(file.filename):
            filepath=join( app.config['TMP_FOLDER'] , thumbnail_filename)
            filepath_last=join( app.config['TMP_FOLDER'] , 'thumbnail_0.png')
            file.save(filepath)
            shutil.copy2(filepath, filepath_last)


class JobThumbnailApi(Resource):
    """Thumbnail interface for the Server
    """

    #: Allowed sizes for thumbnails
    sizes = {'s': (128, 128), 'm': (512, 512), 'l': (1024, 1024)}

    def get(self, job_id, size=None):
        """Returns the last thumbnail for the Job, or a blank image if none.
        If job_id is 0 return the global last thumbnail. It is possible to
        add a suffix to the id (this is why job_id is not strictly an int).
        So, we check if the following suffixes are attached to the image:
        - s
        - m
        - l
        if no suffix is added, we use the original image.
        """

        def make_thumbnail(file_src, file_dst, size='s'):
            """Given an input path, generate a thumbnail with the proper size.
            Returns a file object with the resized thumbnail, or None.
            """

            if size in self.sizes:
                size = self.sizes[size]
            else:
                # Size not supported
                return None

            try:
                im = Image.open(file_src)
                im.thumbnail(size)
                im.save(file_dst)
                logging.debug("Generated thumbnail for {0}".format(file_src))
                return open(file_dst, 'r')
            except IOError, e:
                logging.error("Making the thumbnail: {0}".format(e))
                return None
            else:
                logging.error("Generic error making the thumbnail")
                return None


        def generate(job_id, size):
            """Generate a thumbnail for the requested job id, at the requested
            size. If the size is None, we return the orginal.
            """
            filename = 'thumbnail_{0}.png'.format(job_id)
            path_thumbnail_original = join(app.config['TMP_FOLDER'], filename)
            # Check that the original file exsits
            if os.path.isfile(path_thumbnail_original):
                # Thumbnail file object that is returned by the view
                thumb_file = None
                # Check if we are asking for a thumbnail
                if size:
                    # Define expected path for thumbnail
                    root, ext = os.path.splitext(path_thumbnail_original)
                    path_thumbnail_resized = "{0}.{1}{2}".format(root, size, ext)
                    # Check if the thumbnails has been generated already
                    if os.path.isfile(path_thumbnail_resized):
                        # Modification date for the original image
                        thumb_original_timestamp = time.ctime(
                            os.path.getmtime(path_thumbnail_original))
                        # Modification date for the generated thumbnail
                        thumb_resized_timestamp = time.ctime(
                            os.path.getmtime(path_thumbnail_resized))
                        # Check if the original file is more recent than the resized
                        if thumb_original_timestamp > thumb_resized_timestamp:
                            thumb_file = make_thumbnail(
                                path_thumbnail_original,
                                path_thumbnail_resized,
                                size)
                        else:
                            thumb_file = open(path_thumbnail_resized, 'r')
                    else:
                        # Generate a new thumbnail, defaults to small
                        thumb_file = make_thumbnail(
                            path_thumbnail_original,
                            path_thumbnail_resized,
                            size)

                # If no thumb file is found, open the original image instead
                if not thumb_file:
                    thumb_file = open(str(path_thumbnail_original), 'r')
                return thumb_file.read()
            # If no resized file is available (job did not start or is running)
            else:
                with app.open_resource('static/missing_thumbnail.png') as thumb_file:
                    return thumb_file.read()
            return False

        # The actual image generator that returns the thumbnail or 404
        if job_id[-1:].isalpha():
            real_job_id = job_id[:-1]
            size = job_id[-1:]
        else:
            real_job_id = job_id
            size = None
        bin = generate(real_job_id, size)
        if bin:
            return Response(bin, mimetype='image/png')
        else:
            return '', 404


class JobFileApi(Resource):
    def get(self, job_id):
        """Given a job_id returns the jobzip file
        """
        job = Job.query.get(job_id)
        serverstorage = app.config['SERVER_STORAGE']
        projectpath = join(serverstorage, str(job.project_id))
        jobpath = join(projectpath, str(job_id))
        return send_from_directory(jobpath, 'jobfile_{0}.zip'.format(job_id))


class JobFileOutputApi(Resource):
    def get(self, job_id):
        """Given a task_id returns the output zip file
        """
        serverstorage = app.config['SERVER_STORAGE']
        job = Job.query.get(job_id)
        projectpath = join(serverstorage, str(job.project_id))
        jobpath = join(projectpath, str(job_id))
        zippath = join(jobpath, 'output')
        zname = 'jobfileout_{0}.zip'.format(job_id)
        jobfile = join(jobpath, zname)

        with ZipFile(jobfile, 'w') as jobzip:
            for dirpath, dirnames, filenames in os.walk(zippath):
                for fname in filenames:
                    filepath = join(dirpath, fname)
                    jobzip.write(filepath, fname)

        return send_from_directory(jobpath, zname, as_attachment=True)
