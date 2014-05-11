import json

import os
from os import listdir
from os.path import isfile, join, abspath, dirname
from flask import Blueprint, render_template, abort, jsonify, request

from server.model import *
from server.utils import *
from server import db

shows = Blueprint('shows', __name__)


def delete_show(show_id):
    show = Show.query.get_or_404(show_id)
    db.session.delete(show)
    db.session.commit()
    print('[info] Deleted show', show_id)
    return True


def is_active_show():
    active = Setting.query.filter_by(name = 'active_show').first()
    if active:
        print '[Debug] Active show is not set'
        return False
    else:
        print '[Debug] Active show is currently %s' % Show.query.get(active.value).name
        return True


@shows.route('/')
def index():
    # Here we will add a check to see if we shoud get shows from the
    # local database or if we should query attract for them
    shows = {}
    for show in Show.query.all():
        shows[show.id] = dict(
            name=show.name,
            path_server=show.path_server,
            path_linux=show.path_linux,
            path_osx=show.path_osx)

    return jsonify(shows)


@shows.route('/<int:show_id>')
def get_show(show_id):
    show = Show.query.get_or_404(show_id)
    print('[Debug] Get show %d') % (show.id)
    return jsonify(
        name=show.name,
        path_server=show.path_server,
        path_linux=show.path_linux,
        path_osx=show.path_osx)


@shows.route('/add', methods=['GET', 'POST'])
def shows_add():
    show = Show(
        name=request.form['name'],
        path_server=request.form['path_server'],
        path_linux=request.form['path_linux'],
        path_osx=request.form['path_osx'])
    db.session.add(show)
    db.session.commit()

    is_active = is_active_show()  # Return True or False
    if is_active == 'False':
        set_option = 'True'
    else:
        set_option = request.form['set_show_option']

    if not is_active and set_option == 'False':
        s_active = Setting.query.filter_by(name = 'active_show').first()
        s_active.value = show.id
    elif set_option == 'True':
        s_active = Setting.query.filter_by(name = 'active_show').first()
        s_active.value = show.id
    db.session.add(s_active)
    db.session.commit()
    return jsonify(status='done')


@shows.route('/delete/<int:show_id>', methods=['GET', 'POST'])
def shows_delete(show_id):
    show_setting = Setting.query.filter_by(name = 'active_show').first()
    shots_show = Shot.query.filter_by(show_id = show_id).all()
    for shot_show in shots_show:
        print '[Debug] Deleting shot (%s) for show %s ' % (shot_show.shot_name, shot_show.show_id)
        db.session.delete(shot_show)
        db.session.commit()
    delete_show(show_id)
    shows = Show.query.all()
    compare_show_ids = []
    next = ''
    for a in shows:
        compare_show_ids.append(a.id)
    if len(compare_show_ids) == 0:
        next = 'None'
    else:
        next = max(compare_show_ids)

    if int(show_id) is int(show_setting.value):
        show_setting.value = next
        print '[Debug] Show was active removing show from being active_show'
        db.session.add(show_setting)
        db.session.commit()

    return jsonify(status='done')


@shows.route('/update', methods=['POST'])
def shows_update():
    show = Show.query.get(request.form['show_id'])
    show.path_server = request.form['path_server']
    show.path_linux = request.form['path_linux']
    show.path_osx = request.form['path_osx']
    db.session.add(show)
    db.session.commit()
    return jsonify(status='done')


@shows.route('/render-shows/')
def render_shows():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    render_shows_path = os.path.join(path, 'render_shows/')
    onlyfiles = [f for f in listdir(render_shows_path) if isfile(join(render_shows_path, f))]
    #return str(onlyfiles)
    shows_files = dict(
        shows_files=onlyfiles)

    return jsonify(shows_files)
