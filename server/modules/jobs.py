from flask import Blueprint, render_template, abort, jsonify, request

from model import *
from utils import *

jobs_module = Blueprint('jobs_module', __name__)

def create_job(shot_id, chunk_start, chunk_end):
    Jobs.create(
        shot_id = shot_id,
        worker_id = 12,
        chunk_start = chunk_start,
        chunk_end = chunk_end,
        current_frame = chunk_start,
        status = 'ready',
        priority = 50)


def create_jobs(shot):
    shot_frames_count = shot.frame_end - shot.frame_start
    shot_chunks_remainder = shot_frames_count % shot.chunk_size
    shot_chunks_division = shot_frames_count / shot.chunk_size

    if shot_chunks_remainder == 0:
        print 'we have exact chunks'

        total_chunks = shot_chunks_division
        chunk_start = shot.frame_start
        chunk_end = shot.frame_start + shot.chunk_size - 1

        for chunk in range(total_chunks - 1):
            print 'making chunk for shot', shot.id

            create_job(shot.id, chunk_start, chunk_end)

            chunk_start = chunk_end + 1
            chunk_end = chunk_start + shot.chunk_size - 1

    elif shot_chunks_remainder == shot.chunk_size:
        print 'we have 1 chunk only'

        create_job(shot.id, shot.frame_start, hot.frame_end)

    #elif shot_chunks_remainder > 0 and shot_chunks_remainder < shot.chunk_size:
    else:
        print 'shot_chunks_remainder' , shot_chunks_remainder
        print 'shot_frames_count', shot_frames_count
        print 'shot_chunks_division' , shot_chunks_division

        total_chunks = shot_chunks_division + 1
        chunk_start = shot.frame_start
        chunk_end = shot.frame_start + shot.chunk_size - 1

        for chunk in range(total_chunks - 1):
            print 'making chunk for shot', shot.id

            create_job(shot.id, chunk_start, chunk_end)

            chunk_start = chunk_end + 1
            chunk_end = chunk_start + shot.chunk_size - 1

        chunk_end = chunk_start + shot_chunks_remainder - 1
        create_job(shot.id, chunk_start, chunk_end)


def dispatch_jobs():
    for worker in Workers.select().where(Workers.status == 'available'):

        # pick the job with the highest priority (it means the lowest number)
        job = Jobs.select().where(
            Jobs.status == 'ready'
        ).order_by(Jobs.priority.desc()).limit(1).get()

        job.status = 'running'
        job.save()

        # now we build the actual job to send to the worker
        job_parameters = {
            'pre-run' : 'svn up or other things',
            'command' : 'blender_path -b /filepath.blend -o /render_out -a',
            'post-frame' : 'post frame',
            'post-run' : 'clear variables, empty /tmp'
        }

        # and we send the job to the worker
        http_request(worker.ip_address, '/run_job', job_parameters)

        print job.status


def delete_job(job_id):
    # At the moment this function is not used anywhere
    try:
        job = Jobs.get(Jobs.id == job_id)
    except Exception, e:
        print e
        return 'error'
    job.delete_instance()
    print 'Deleted job', job_id


def delete_jobs(shot_id):
    delete_query = Jobs.delete().where(Jobs.shot_id == shot_id)
    delete_query.execute()
    print 'All jobs deleted for shot', shot_id


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

        jobs[job.id] = {
            "shot_id" : job.shot_id,
            "chunk_start" : job.chunk_start,
            "chunk_end" : job.chunk_end,
            "current_frame" : job.current_frame,
            "status" : job.status,
            "percentage_done" : percentage_done,
            "priority" : job.priority}
    return jsonify(jobs)
