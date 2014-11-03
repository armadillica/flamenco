import json

import os
from os import listdir
from os.path import isfile, join, abspath, dirname
from flask import Blueprint, render_template, abort, jsonify, request

from server.model import *
from server.utils import *
from server import db

projects = Blueprint('projects', __name__)


def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    print('[info] Deleted project', project_id)
    return True


def is_active_project():
    active = Setting.query.filter_by(name = 'active_project').first()
    if not active or active.value == 'None':
        print '[Debug] Active project is not set'
        return False
    else:
        print '[Debug] Active project is currently %s' % Project.query.get(active.value).name
        return True


@projects.route('/')
def index():
    # Here we will add a check to see if we shoud get projects from the
    # local database or if we should query attract for them
    projects = {}
    for project in Project.query.all():
        projects[project.id] = dict(
            name=project.name,
            path_server=project.path_server,
            path_linux=project.path_linux,
            path_win=project.path_win,
            path_osx=project.path_osx)

    return jsonify(projects)


@projects.route('/<int:project_id>')
def get_project(project_id):
    project = Project.query.get_or_404(project_id)
    print('[Debug] Get project %d') % (project.id)
    return jsonify(
        name=project.name,
        path_server=project.path_server,
        path_linux=project.path_linux,
		path_win=project.path_win,
        path_osx=project.path_osx)


@projects.route('/add', methods=['GET', 'POST'])
def projects_add():
    project = Project(
        name=request.form['name'],
        path_server=request.form['path_server'],
        path_linux=request.form['path_linux'],
        path_win=request.form['path_win'],
        path_osx=request.form['path_osx'])
    db.session.add(project)
    db.session.commit()

    is_active = is_active_project()  # Return True or False
    if is_active == 'False':
        set_option = 'True'
    else:
        set_option = request.form['set_project_option']

    if (not is_active and set_option == 'False') or set_option == 'True':
        s_active = Setting.query.filter_by(name = 'active_project').first()
        if s_active == None:
            s_active = Setting(
                name = 'active_project',
                value = project.id)
        else:
            s_active.value = project.id
    #elif set_option == 'True':
    #    s_active = Setting.query.filter_by(name = 'active_project').first()
    #    s_active.value = project.id

    db.session.add(s_active)
    db.session.commit()
    return jsonify(status='done')


@projects.route('/delete/<int:project_id>', methods=['GET', 'POST'])
def projects_delete(project_id):
    project_setting = Setting.query.filter_by(name = 'active_project').first()
    shots_project = Shot.query.filter_by(project_id = project_id).all()
    for shot_project in shots_project:
        print '[Debug] Deleting shot (%s) for project %s ' % (shot_project.shot_name, shot_project.project_id)
        db.session.delete(shot_project)
        db.session.commit()
    delete_project(project_id)
    projects = Project.query.all()
    if len(projects) > 0:
        compare_project_ids = []
        next = ''
        for a in projects:
            compare_project_ids.append(a.id)
        if len(compare_project_ids) == 0:
            next = 'None'
        else:
            next = max(compare_project_ids)

        if int(project_id) is int(project_setting.value):
            project_setting.value = next
            print '[Debug] Project was active removing project from being active_project'
            db.session.add(project_setting)
            db.session.commit()
    else:
        project_setting.value = 'None'
        print '[Debug] There is no active project now'
        db.session.add(project_setting)
        db.session.commit()

    return jsonify(status='done')


@projects.route('/update', methods=['POST'])
def projects_update():
    project = Project.query.get(request.form['project_id'])
    project.path_server = request.form['path_server']
    project.path_linux = request.form['path_linux']
    project.path_win = request.form['path_win']
    project.path_osx = request.form['path_osx']
    db.session.commit()
    return jsonify(status='done')


@projects.route('/render-projects/')
def render_projects():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    render_projects_path = os.path.join(path, 'render_projects/')
    onlyfiles = [f for f in listdir(render_projects_path) if isfile(join(render_projects_path, f))]
    #return str(onlyfiles)
    projects_files = dict(
        projects_files=onlyfiles)

    return jsonify(projects_files)
