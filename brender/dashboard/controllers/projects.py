import json

from flask import flash
from flask import render_template
from flask import request
from flask import Blueprint
from flask import url_for
from flask import redirect

from dashboard import app
from dashboard import list_integers_string
from dashboard import check_connection
from dashboard import http_server_request

projects = Blueprint('projects', __name__)


@projects.route('/')
def index():
    #projects = http_server_request('get', '/projects')
    settings = http_server_request('get', '/settings')

    projects = http_server_request('get', '/projects')

    return render_template('projects/index.html',
        projects=projects,
        settings=settings,
        title='projects')


@projects.route('/update/<project_id>', methods=['POST'])
def update(project_id):

    params = dict(
        path_server=request.form['path_server'],
        path_linux=request.form['path_linux'],
        path_win=request.form['path_win'],
        path_osx=request.form['path_osx'],
        render_path_server=request.form['render_path_server'],
        render_path_linux=request.form['render_path_linux'],
        render_path_win=request.form['render_path_win'],
        render_path_osx=request.form['render_path_osx'])

    projects = http_server_request('put', '/projects/' + project_id, params)
    print projects
    # http_server_request('get', '/projects/update', params)

    return redirect(url_for('projects.index'))


@projects.route('/delete/<project_id>', methods=['GET', 'POST'])
def delete(project_id):
    http_server_request('delete', '/projects/' + project_id)
    #http_server_request('get', '/projects/delete/' + project_id)
    return redirect(url_for('projects.index'))


@projects.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        params = dict(
            name=request.form['name'],
            path_server=request.form['path_server'],
            path_linux=request.form['path_linux'],
            path_win=request.form['path_win'],
            path_osx=request.form['path_osx'],
            render_path_server=request.form['render_path_server'],
            render_path_linux=request.form['render_path_linux'],
            render_path_win=request.form['render_path_win'],
            render_path_osx=request.form['render_path_osx'],
            is_active=request.form['set_project_option'])
        http_server_request('post', '/projects', params)
        return redirect(url_for('projects.index'))
    else:
        render_settings = http_server_request('get', '/settings/render')
        projects = http_server_request('get', '/projects')
        settings = http_server_request('get', '/settings')
        return render_template('projects/add_modal.html',
                        render_settings=render_settings,
                        settings=settings,
                        projects=projects)
