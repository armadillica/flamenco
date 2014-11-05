import os

from flask import (abort,
                   Blueprint,
                   jsonify,
                   render_template,
                   request)

# TODO(sergey): Generally not a good idea to import *
from server.model import *
from server.utils import *
from workers import *
from server import db

jobs = Blueprint('jobs', __name__)


def create_job(shot_id, chunk_start, chunk_end):
    job = Job(shot_id=shot_id,
        worker_id=12,
        chunk_start=chunk_start,
        chunk_end=chunk_end,
        current_frame=chunk_start,
        status='ready',
        priority=50)
    db.session.add(job)
    db.session.commit()


def create_jobs(shot):
    shot_frames_count = shot.frame_end - shot.frame_start + 1
    shot_chunks_remainder = shot_frames_count % shot.chunk_size
    shot_chunks_division = shot_frames_count / shot.chunk_size

    if shot_chunks_remainder == 0:
        print('we have exact chunks')

        total_chunks = shot_chunks_division
        chunk_start = shot.frame_start
        chunk_end = shot.frame_start + shot.chunk_size - 1

        for chunk in range(total_chunks):
            print('making chunk for shot', shot.id)

            create_job(shot.id, chunk_start, chunk_end)

            chunk_start = chunk_end + 1
            chunk_end = chunk_start + shot.chunk_size - 1

    elif shot_chunks_remainder == shot.chunk_size:
        print('we have 1 chunk only')

        create_job(shot.id, shot.frame_start, shot.frame_end)

    #elif shot_chunks_remainder > 0 and \
    #     shot_chunks_remainder < shot.chunk_size:
    else:
        print('shot_chunks_remainder', shot_chunks_remainder)
        print('shot_frames_count', shot_frames_count)
        print('shot_chunks_division', shot_chunks_division)

        total_chunks = shot_chunks_division + 1
        chunk_start = shot.frame_start
        chunk_end = shot.frame_start + shot.chunk_size - 1

        for chunk in range(total_chunks - 1):
            print('making chunk for shot', shot.id)

            create_job(shot.id, chunk_start, chunk_end)

            chunk_start = chunk_end + 1
            chunk_end = chunk_start + shot.chunk_size - 1

        chunk_end = chunk_start + shot_chunks_remainder - 1
        create_job(shot.id, chunk_start, chunk_end)


def start_job(worker, job):
    """Execute a single job
    We pass worker and job as objects (and at the moment we use a bad
    way to get the additional shot information - should be done with join)
    """

    shot = Shot.query.filter_by(id = job.shot_id).first()
    project = Project.query.filter_by(id = shot.project_id).first()

    filepath = shot.filepath

    if 'Darwin' in worker.system:
        setting_blender_path = Setting.query.filter_by(name='blender_path_osx').first()
        setting_render_settings = Setting.query.filter_by(name='render_settings_path_osx').first()
        filepath = os.path.join(project.path_osx, shot.filepath)
    elif 'Windows' in worker.system:
        setting_blender_path = Setting.query.filter_by(name='blender_path_win').first()
        setting_render_settings = Setting.query.filter_by(name='render_settings_path_win').first()
        filepath = os.path.join(project.path_win, shot.filepath)
    else:
        setting_blender_path = Setting.query.filter_by(name='blender_path_linux').first()
        setting_render_settings = Setting.query.filter_by(name='render_settings_path_linux').first()
        filepath = os.path.join(project.path_linux, shot.filepath)

    if setting_blender_path is None:
        print '[Debug] blender path is not set'

    blender_path = setting_blender_path.value

    if setting_render_settings is None:
        print '[Debug] render settings is not set'

    render_settings = os.path.join(
        setting_render_settings.value ,
        shot.render_settings)

    worker_ip_address = worker.ip_address

    """
    Additional params for future reference

    job_parameters = {'pre-run': 'svn up or other things',
                      'command': 'blender_path -b ' +
                                 '/filepath.blend -o /render_out -a',
                      'post-frame': 'post frame',
                      'post-run': 'clear variables, empty /tmp'}
    """

    params = {'job_id': job.id,
              'file_path': filepath,
              'blender_path': blender_path,
              'render_settings': render_settings,
              'start': job.chunk_start,
              'end': job.chunk_end}

    http_request(worker_ip_address, '/execute_job', params)
    #  get a reply from the worker (running, error, etc)

    job.status = 'running'
    db.session.add(job)

    shot.current_frame = job.chunk_end
    db.session.add(shot)
    db.session.commit()

    return 'Job started'


def dispatch_jobs(shot_id = None):
    workers = Worker.query.\
        filter_by(status='enabled').\
        filter_by(connection='online').\
        all()
    for worker in workers:
        # pick the job with the highest priority (it means the lowest number)

        job = Job.query.\
            filter_by(status='ready').\
            order_by(Job.priority.desc()).\
            first()

        if job:
            job.status = 'running'
            db.session.add(job)
            db.session.commit()
            start_job(worker, job)
        #else:
        #    print '[error] Job does not exist'

        """Legacy code
        job = None # will figure out another way
        try:
            job = Jobs.select().where(
                Jobs.status == 'ready'
            ).order_by(Jobs.priority.desc()).limit(1).get()

            job.status = 'running'
            job.save()
        except Jobs.DoesNotExist:
            print '[error] Job does not exist'
        if job:
            start_job(worker, job)
        """

def delete_job(job_id):
    # At the moment this function is not used anywhere
    try:
        job = Jobs.query.get(job_id)
    except Exception, e:
        print(e)
        return 'error'
    job.delete_instance()
    print('Deleted job', job_id)


def delete_jobs(shot_id):
    jobs = Job.query.filter_by(shot_id=shot_id).delete()
    print('All jobs deleted for shot', shot_id)


def start_jobs(shot_id):
    """[DEPRECATED] We start all the jobs for a specific shot
    """
    for job in Jobs.select().where(Jobs.shot_id == shot_id,
                                   Jobs.status == 'ready'):
        print(start_job(job.id))


def stop_job(job_id):
    """Stop a single job
    """
    job = Job.query.get(job_id)
    job.status = 'ready'
    db.session.add(job)
    db.session.commit()

    return 'Job stopped'


def stop_jobs(shot_id):
    """We stop all the jobs for a specific shot
    """
    jobs = Job.query.\
        filter_by(shot_id = shot_id).\
        filter_by(status = 'running').\
        all()

    for job in jobs:
        print(stop_job(job.id))


@jobs.route('/')
def index():
    from decimal import Decimal
    jobs = {}
    percentage_done = 0
    for job in Job.query.all():

        frame_count = job.chunk_end - job.chunk_start + 1
        current_frame = job.current_frame - job.chunk_start + 1
        percentage_done = Decimal(current_frame) / Decimal(frame_count) * Decimal(100)
        percentage_done = round(percentage_done, 1)
        jobs[job.id] = {"shot_id": job.shot_id,
                        "chunk_start": job.chunk_start,
                        "chunk_end": job.chunk_end,
                        "current_frame": job.current_frame,
                        "status": job.status,
                        "percentage_done": percentage_done,
                        "priority": job.priority}
    return jsonify(jobs)


@jobs.route('/update', methods=['POST'])
def jobs_update():
    job_id = request.form['id']
    status = request.form['status'].lower()
    if status in ['finished']:
        job = Job.query.get(job_id)
        shot = Shot.query.get(job.shot_id)
        job.status = 'finished'
        db.session.add(shot)

        if job.chunk_end == shot.frame_end:
            shot.status = 'completed'
            # this can be added when we update the shot for every
            # frame rendered
            # if job.current_frame == shot.frame_end:
            #     shot.status = 'finished'
            db.session.add(shot)
        db.session.commit()

    dispatch_jobs()

    return jsonify(reponse='Job Updated')
