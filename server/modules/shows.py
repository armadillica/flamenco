import json

import os
from os import listdir
from os.path import isfile, join, abspath, dirname
from flask import Blueprint, render_template, abort, jsonify, request

from server.model import *
from server.utils import *

shows_module = Blueprint('shows_module', __name__)


def delete_show(show_id):
    try:
        show = Shows.get(Shows.id == show_id)
    except Shows.DoesNotExist:
        print('[error] Show not found')
        return 'error'
    show.delete_instance()
    print('[info] Deleted show', show_id)

'''
Checks to see if a show is set as active_show
if yes then True
if no then False
'''


def is_active_show():
    active = Settings.get(Settings.name == 'active_show')
    if active.value == 'None':
        print '[Debug] Active show is not set'
        return False
    else:
        print '[Debug] Active show is currently %s' % Shows.get(Shows.id == active.value).name
        return True


@shows_module.route('/shows/')
def shows():
    # Here we will add a check to see if we shoud get shows from the
    # local database or if we should query attract for them
    shows = {}
    for show in Shows.select():
        shows[show.id] = dict(
            name=show.name,
            path_server=show.path_server,
            path_linux=show.path_linux,
            path_osx=show.path_osx)

    return jsonify(shows)


@shows_module.route('/shows/<int:show_id>')
def get_show(show_id):
    try:
        show = Shows.get(Shows.id == show_id)
        print('[Debug] Get show %d') % (show.id)
    except Shows.DoesNotExist:
        print '[Error] Show not found'
        return 'Show %d not found' % show_id

    return jsonify(
        name=show.name,
        path_server=show.path_server,
        path_linux=show.path_linux,
        path_osx=show.path_osx)


@shows_module.route('/shows/add', methods=['GET', 'POST'])
def shows_add():
    show = Shows.create(
        name=request.form['name'],
        path_server=request.form['path_server'],
        path_linux=request.form['path_linux'],
        path_osx=request.form['path_osx'])
    show.save()

    is_active = is_active_show()  # Return True or False
    if is_active == 'False':
        set_option = 'True'
    else:
        set_option = request.form['set_show_option']

    if not is_active and set_option == 'False':
        s_active = Settings.get(Settings.name == 'active_show')
        s_active.value = show.id
        s_active.save()
    elif set_option == 'True':
        s_active = Settings.get(Settings.name == 'active_show')
        s_active.value = show.id
        s_active.save()
    return 'done'


@shows_module.route('/shows/delete/<int:show_id>', methods=['GET', 'POST'])
def shows_delete(show_id):
    show_setting = Settings.get(Settings.name == 'active_show')
    shots_show = Shots.select().where(Shots.show_id == show_id)
    for shot_show in shots_show:
        print '[Debug] Deleting shot (%s) for show %s ' % (shot_show.shot_name, shot_show.show_id)
        shot_show.delete_instance()
    delete_show(show_id)
    shows = Shows.select()
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
        show_setting.save()

    return 'done'


@shows_module.route('/shows/update', methods=['POST'])
def shows_update():
    '''
    not quite sure if we need a try statement here
    because if we are updating a show it should exist right? lol?
    '''
    show = Shows.get(Shows.id == request.form['show_id'])
    show.path_server = request.form['path_server']
    show.path_linux = request.form['path_linux']
    show.path_osx = request.form['path_osx']
    show.save()
    return 'done'


@shows_module.route('/render-shows/')
def render_shows():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    render_shows_path = os.path.join(path, 'render_shows/')
    onlyfiles = [f for f in listdir(render_shows_path) if isfile(join(render_shows_path, f))]
    #return str(onlyfiles)
    shows_files = dict(
        shows_files=onlyfiles)

    return jsonify(shows_files)
