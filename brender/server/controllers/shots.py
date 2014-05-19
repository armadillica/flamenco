from flask import Blueprint, render_template, abort, jsonify, request

import os
from os import listdir
from os.path import isfile, isdir, join, abspath, dirname

from server.model import *
from server.utils import *
from jobs import *
from server import db

shots = Blueprint('shots', __name__)


def delete_shot(shot_id):
    shot = Shot.query.get(shot_id)
    if shot:
        db.session.delete(shot)
        db.session.commit()
        print('[info] Deleted shot', shot_id)
    else:
        print('[error] Shot not found')
        return 'error'


@shots.route('/')
def index():
    shots = {}
    for shot in Shot.query.all():
        percentage_done = 0
        frame_count = shot.frame_end - shot.frame_start + 1
        current_frame = shot.current_frame - shot.frame_start + 1
        percentage_done = float(current_frame) / float(frame_count) * float(100)
        percentage_done = round(percentage_done, 1)

        if percentage_done == 100:
            shot.status = 'completed'

        shots[shot.id] = {
                          "id": shot.id,
                          "frame_start": shot.frame_start,
                          "frame_end": shot.frame_end,
                          "current_frame": shot.current_frame,
                          "status": shot.status,
                          "shot_name": shot.name,
                          "percentage_done": percentage_done,
                          "render_settings": shot.render_settings}
    return jsonify(shots)


@shots.route('/browse/', defaults={'path': ''})
@shots.route('/browse/<path:path>',)
def shots_browse(path):
    """We browse the production folder on the server.
    The path value gets appended to the active_show path value. The result is returned
    in JSON format.
    """
    active_show = Setting.query.filter_by(name = 'active_show').first()
    active_show = Show.query.get(active_show.value)

    # path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # render_settings_path = os.path.join(path, 'render_settings/')

    absolute_path_root = active_show.path_server
    parent_path = ''

    if path != '':
        absolute_path_root = os.path.join(absolute_path_root, path)
        parent_path = os.pardir

    # print(active_show.path_server)
    # print(listdir(active_show.path_server))

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
        project_path_server=active_show.path_server,
        parent_path=parent_path,
        # items=items,
        items_list=items_list)

    return jsonify(project_files)


@shots.route('/update', methods=['POST'])
def shot_update():
    status = request.form['status']
    # TODO parse
    shot_ids = request.form['id']
    shots_list = list_integers_string(shot_ids)
    for shot_id in shots_list:
        print("updating shot %s = %s " % (shot_id, status))
    return jsonify(status='Shots updated')


@shots.route('/start', methods=['POST'])
def shots_start():
    shot_ids = request.form['id']
    shots_list = list_integers_string(shot_ids)
    for shot_id in shots_list:
        shot = Shot.query.get(shot_id)
        if shot:
            if shot.status != 'running':
                shot.status = 'running'
                db.session.add(shot)
                db.session.commit()
                print ('[debug] Dispatching jobs')       
        else:
            print('[error] Shot not found')
            response = 'Shot %d not found' % shot_id
            return jsonify(response=response)
    dispatch_jobs()        
    return jsonify(
        shot_ids=shot_ids,
        status='running')


@shots.route('/stop', methods=['POST'])
def shots_stop():
    shot_ids = request.form['id']
    shots_list = list_integers_string(shot_ids)
    for shot_id in shots_list:
        print '[info] Working on shot', shot_id
        # first we delete the associated jobs (no foreign keys)
        shot = Shot.query.get(shot_id)
        if shot:
            if shot.status != 'stopped':
                stop_jobs(shot.id)
                shot.status = 'stopped'
                db.session.add(shot)
                db.session.commit()
        else:
            print('[error] Shot not found')
            response = 'Shot %d not found' % shot_id
            return jsonify(response=response)

    return jsonify(
        shot_ids=shot_ids,
        status='stopped')


@shots.route('/reset', methods=['POST'])
def shots_reset():
    shot_ids = request.form['id']
    shots_list = list_integers_string(shot_ids)
    for shot_id in shots_list:
        shot = Shot.query.get(shot_id)
        if shot:
            if shot.status == 'running':
                response = 'Shot %d is running' % shot_id
                return jsonify(response=response)
            else:
                shot.current_frame = shot.frame_start
                shot.status = 'ready'
                db.session.add(shot)
                db.session.commit()

                delete_jobs(shot.id)
                create_jobs(shot)
        else:
            print('[error] Shot not found')
            response = 'Shot %d not found' % shot_id
            return jsonify(response=response)

    return jsonify(
        shot_ids=shots_list,
        status='ready')


@shots.route('/add', methods=['POST'])
def shot_add():
    print('adding shot')

    shot = Shot(
        show_id=int(request.form['show_id']),
        frame_start=int(request.form['frame_start']),
        frame_end=int(request.form['frame_end']),
        chunk_size=int(request.form['chunk_size']),
        current_frame=int(request.form['frame_start']),
        filepath=request.form['filepath'],
        name=request.form['shot_name'],
        render_settings=request.form['render_settings'],
        status='running',
        priority=10)

    db.session.add(shot)
    db.session.commit()

    print('parsing shot to create jobs')

    create_jobs(shot)

    print('refresh list of available workers')

    dispatch_jobs(shot.id)

    return jsonify(status='done')


@shots.route('/delete', methods=['POST'])
def shots_delete():
    shot_ids = request.form['id']
    shots_list = list_integers_string(shot_ids)
    for shot_id in shots_list:
        print('working on', shot_id, '-', str(type(shot_id)))
        # first we delete the associated jobs (no foreign keys)
        delete_jobs(shot_id)
        # then we delete the shot
        delete_shot(shot_id)
    return jsonify(status='done')
