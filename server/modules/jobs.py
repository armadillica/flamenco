from flask import (abort,
                   Blueprint,
                   jsonify,
                   render_template,
                   request)

# TODO(sergey): Generally not a good idea to import *
from model import *
from utils import *
from workers import *

jobs_module = Blueprint('jobs_module', __name__)


def create_job(shot_id, chunk_start, chunk_end):
    Jobs.create(shot_id=shot_id,
                worker_id=12,
                chunk_start=chunk_start,
                chunk_end=chunk_end,
                current_frame=chunk_start,
                status='ready',
                priority=50)


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
    """
    Execute a single job
    We pass worker and job as objects (and at the moment we use a bad
    way to get the additional shot information - should be done with join)
    """

    shot = Shots.get(Shots.id == job.shot_id)

    if 'Darwin' in worker.system:
        setting = Settings.get(Settings.name == 'blender_path_osx')
        blender_path = setting.value
    else:
        setting = Settings.get(Settings.name == 'blender_path_linux')
        blender_path = setting.value

    worker_ip_address = worker.ip_address

    """
    Additiona params for future reference

    job_parameters = {'pre-run': 'svn up or other things',
                      'command': 'blender_path -b ' +
                                 '/filepath.blend -o /render_out -a',
                      'post-frame': 'post frame',
                      'post-run': 'clear variables, empty /tmp'}
    """

    params = {'job_id': job.id,
              'file_path': shot.filepath,
              'blender_path': blender_path,
              'start': job.chunk_start,
              'end': job.chunk_end}

    http_request(worker_ip_address, '/execute_job', params)
    #  get a reply from the worker (running, error, etc)

    job.status = 'running'
    job.save()

    shot.current_frame = job.chunk_end
    shot.save()

    return 'Job started'


def dispatch_jobs(shot_id = None):
    for worker in Workers.select().where(
        (Workers.status == 'enabled') & (Workers.connection == 'online')):

        # pick the job with the highest priority (it means the lowest number)
        job = Jobs.select().where(
            Jobs.status == 'ready'
        ).order_by(Jobs.priority.desc()).limit(1).get()

        job.status = 'running'
        job.save()

        start_job(worker, job)


def delete_job(job_id):
    # At the moment this function is not used anywhere
    try:
        job = Jobs.get(Jobs.id == job_id)
    except Exception, e:
        print(e)
        return 'error'
    job.delete_instance()
    print('Deleted job', job_id)


def delete_jobs(shot_id):
    delete_query = Jobs.delete().where(Jobs.shot_id == shot_id)
    delete_query.execute()
    print('All jobs deleted for shot', shot_id)


def start_jobs(shot_id):
    """
    [DEPRECATED] We start all the jobs for a specific shot
    """
    for job in Jobs.select().where(Jobs.shot_id == shot_id,
                                   Jobs.status == 'ready'):
        print(start_job(job.id))


def stop_job(job_id):
    """
    Stop a single job
    """
    job = Jobs.get(Jobs.id == job_id)
    job.status = 'ready'
    job.save()

    return 'Job stopped'


def stop_jobs(shot_id):
    """
    We stop all the jobs for a specific shot
    """
    for job in Jobs.select().where(Jobs.shot_id == shot_id,
                                   Jobs.status == 'running'):
        print(stop_job(job.id))


@jobs_module.route('/jobs/')
def jobs():
    jobs = {}
    for job in Jobs.select():

        if job.chunk_start == job.current_frame:
            percentage_done = 0
        else:
            frame_count = job.chunk_end - job.chunk_start + 1
            current_frame = job.current_frame - job.chunk_start + 1
            percentage_done = 100 / frame_count * current_frame
        jobs[job.id] = {"shot_id": job.shot_id,
                        "chunk_start": job.chunk_start,
                        "chunk_end": job.chunk_end,
                        "current_frame": job.current_frame,
                        "status": job.status,
                        "percentage_done": percentage_done,
                        "priority": job.priority}
    return jsonify(jobs)


@jobs_module.route('/jobs/update', methods=['POST'])
def jobs_update():
    job_id = request.form['id']
    status = request.form['status'].lower()
    if status in ['finished']:
        job = Jobs.get(Jobs.id == job_id)
        job.status = 'finished'
        job.save()
    try:
        dispatch_jobs()
    except:
        return "couldnt dispatch jobs / update jobs"
    return "job updated"
