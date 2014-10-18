import json
from flask import (flash,
                   render_template,
                   request,
                   Blueprint)

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
