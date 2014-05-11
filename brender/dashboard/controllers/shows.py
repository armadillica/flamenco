import json
from flask import (flash,
                   render_template,
                   request,
                   Blueprint,
                   url_for,
                   redirect)

from dashboard import app
from dashboard import http_request, list_integers_string, check_connection

# TODO: find a better way to fill/use this variable
BRENDER_SERVER = app.config['BRENDER_SERVER']


# Name of the Blueprint
shows = Blueprint('shows', __name__)


@shows.route('/')
def index():
    shows = http_request(BRENDER_SERVER, '/shows')

    shows = json.loads(shows)
    settings = json.loads(http_request(BRENDER_SERVER, '/settings/'))

    return render_template('shows/index.html', shows=shows, settings=settings, title='shows')


@shows.route('/update', methods=['POST'])
def update():

    params = dict(
        show_id=request.form['show_id'],
        path_server=request.form['path_server'],
        path_linux=request.form['path_linux'],
        path_osx=request.form['path_osx'])

    http_request(BRENDER_SERVER, '/shows/update', params)

    return redirect(url_for('shows.index'))


@shows.route('/delete/<show_id>', methods=['GET', 'POST'])
def delete(show_id):
    http_request(BRENDER_SERVER, '/shows/delete/' + show_id)
    return redirect(url_for('shows.index'))


@shows.route('/add', methods=['GET', 'POST'])
def add():
    print 'inside shows_add dashboard'
    if request.method == 'POST':
        params = dict(
            name=request.form['name'],
            path_server=request.form['path_server'],
            path_linux=request.form['path_linux'],
            path_osx=request.form['path_osx'],
            set_show_option=request.form['set_show_option'])
        print params
        http_request(BRENDER_SERVER, '/shows/add', params)
        return redirect(url_for('shows.index'))
    else:
        render_settings = json.loads(http_request(BRENDER_SERVER, '/settings/render'))
        shows = json.loads(http_request(BRENDER_SERVER, '/shows/'))
        settings = json.loads(http_request(BRENDER_SERVER, '/settings/'))
        return render_template('shows/add_modal.html',
                        render_settings=render_settings,
                        settings=settings,
                        shows=shows)
