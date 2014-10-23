import json
from flask import (flash,
                   render_template,
                   request,
                   Blueprint,
                   jsonify,
                   url_for,
                   redirect)
import os
from dashboard import app
from dashboard import http_request, list_integers_string, check_connection

# TODO: find a better way to fill/use this variable
BRENDER_SERVER = app.config['BRENDER_SERVER']


# Name of the Blueprint
settings = Blueprint('settings', __name__)


@settings.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        params = request.form
        http_request(BRENDER_SERVER, '/settings/update', params)

    projects = http_request(BRENDER_SERVER, '/projects/')
    settings = http_request(BRENDER_SERVER, '/settings/')
    return render_template('settings/index.html',
                           title='settings',
                           settings=settings,
                           projects=projects)


@settings.route('/render/', methods=['GET'])
def render():
    render_settings = http_request(BRENDER_SERVER, '/settings/render')
    return render_template('settings/render.html',
                           title='render settings',
                           render_settings=render_settings)

@settings.route('/render/<sname>', methods=['GET', 'POST'])
def render_settings_edit(sname):
  if request.method == 'GET':
    result = http_request(BRENDER_SERVER, '/settings/render/' + sname)
    return result['text']
  elif request.method == 'POST':
    content = request.json
    params = dict(
      text=str(content['text'])
    )
    http_request(BRENDER_SERVER, '/settings/render/' + sname, params)
    return 'done'

@settings.route('/render/add', methods=['GET', 'POST'])
def render_settings_add():
  if request.method == 'GET':
    return render_template('settings/add_render_modal.html')
  elif request.method == 'POST':
    filename = request.form['render_setting_file_name'] + '.py'
    params = {'filename': filename}
    http_request(BRENDER_SERVER, '/settings/render/add/', params)
    return redirect(url_for('settings.render'))

@settings.route('/status/', methods=['GET'])
def status():
    try:
        server_status = check_connection(BRENDER_SERVER)
        server_stats = http_request(BRENDER_SERVER, '/stats')
    except :
        server_status = 'offline'
        server_stats = ''
    return render_template('settings/status.html',
        title='server status',
        server_stats=server_stats,
        server_status=server_status)
