from flask import Blueprint, render_template, abort, jsonify, request

from model import *
from jobs import *
from utils import *

shots_module = Blueprint('shots_module', __name__)

def delete_shot(shot_id):
	try:
		shot = Shots.get(Shots.id == shot_id)
	except Exception, e:
	    print e
	    return 'error'
	shot.delete_instance()
	print 'Deleted shot', shot_id


@shots_module.route('/shots/')
def shots():
    shots = {}
    for shot in Shots.select():
        if shot.frame_start == shot.current_frame:
            percentage_done = 0
        else:
            frame_count = shot.frame_end - shot.frame_start + 1
            current_frame = shot.current_frame - shot.frame_start + 1
            percentage_done = 100 / frame_count * current_frame

        shots[shot.id] = {
            "frame_start" : shot.frame_start,
            "frame_end" : shot.frame_end,
            "current_frame" : shot.current_frame,
            "status" : shot.status,
            "shot_name" : shot.shot_name,
            "percentage_done" : percentage_done,
            "render_settings" : shot.render_settings}
    return jsonify(shots)


@shots_module.route('/shots/update', methods=['POST'])
def shot_update():
    #status = request.form['status']
    # TODO parse 
    shot_ids = request.form['id']
    shots_list = list_integers_string(shot_ids)
    for shot_id in shots_list:
    	#print "updating shot %s = %s " % (shot_id,status)
    	print "updating shot %s " % shot_id
    return "TEMP done updating shots "


@shots_module.route('/shots/start/<int:shot_id>')
def shot_start(shot_id):
    try:
        shot = Shots.get(Shots.id == shot_id)
    except Exception, e:
        print e , '--> Shot not found'
        return 'Shot %d not found' % shot_id

    if shot.status == 'started':
        return 'Shot &d already started'  % shot_id
    else:
        shot.status = 'started'
        shot.save()
        #http_request()
        return 'Shot &d started'  % shot_id

@shots_module.route('/shots/add', methods=['POST'])
def shot_add():
    print 'adding shot'

    shot = Shots.create(
        production_shot_id = 1,
        frame_start = int(request.form['frame_start']),
        frame_end = int(request.form['frame_end']),
        chunk_size = int(request.form['chunk_size']),
        current_frame = int(request.form['frame_start']),
        filepath = request.form['filepath'],
        shot_name = request.form['shot_name'],
        render_settings = 'will refer to settings table',
        status = 'running',
        priority = 10,
        owner = 'fsiddi')

    print 'parsing shot to create jobs'

    create_jobs(shot)

    print 'refresh list of available workers'

    dispatch_jobs()

    return 'done'

@shots_module.route('/shots/delete', methods=['POST'])
def shots_delete():
    shot_ids = request.form['id']
    shots_list =list_integers_string(shot_ids)
    for shot_id in shots_list:
        print 'working on', shot_id, '-', str(type(shot_id))
        # first we delete the associated jobs (no foreign keys)
        delete_jobs(shot_id)
        # then we delete the shot
        delete_shot(shot_id)        
    return 'done'
