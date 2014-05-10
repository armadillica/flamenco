import glob
import json
import os
import time
import urllib
from os import listdir
from os.path import isfile, join, abspath
from glob import iglob
from flask import (flash,
                   Flask,
                   jsonify,
                   redirect,
                   render_template,
                   request,
                   url_for,
                   make_response,
                   Blueprint)

from dashboard import app

# TODO: find a better way to fill/use this variable
BRENDER_SERVER = app.config['BRENDER_SERVER']

def http_request(ip_address, method, post_params=False):
    # post_params must be a dictionnary
    if post_params:
        params = urllib.urlencode(post_params)
        f = urllib.urlopen('http://' + ip_address + method, params)
    else:
        f = urllib.urlopen('http://' + ip_address + method)

    print('message sent, reply follows:')
    return f.read()


def list_integers_string(string_list):
    """Accepts comma separated string list of integers
    """
    integers_list = string_list.split(',')
    integers_list = map(int, integers_list)
    return integers_list


# Name of the Blueprint
shots = Blueprint('shots', __name__)

@shots.route('/')
def index():
    shots = http_request(BRENDER_SERVER, '/shots')
    #print(shots)
    shots = json.loads(shots)
    shots_list = []

    for key, val in shots.iteritems():
        val['checkbox'] = '<input type="checkbox" value="' + key + '" />'
        shots_list.append({
            "DT_RowId": "shot_" + str(key),
            "0": val['checkbox'],
            "1": key,
            "2": val['shot_name'],
            "3": val['percentage_done'],
            "4": val['render_settings'],
            "5": val['status']})
        #print(v)

    entries = json.dumps(shots_list)

    return render_template('shots/index.html', entries=entries, title='shots')


@shots.route('/<shot_id>')
def shot(shot_id):
    print '[Debug] shot_id is %s' % shot_id
    shot = None
    try:
        shots = http_request(BRENDER_SERVER, '/shots')
        shots = json.loads(shots)
    except KeyError:
        print 'shot doesnt exist'
    if shot_id in shots:
        for key, val in shots.iteritems():
            if shot_id in key:
                shot = shots[shot_id]

    if shot:
        shot = shots[shot_id]
        return render_template('shots/view.html', shot=shot)
    else:
        return make_response('shot ' + shot_id + ' doesnt exist')


@shots.route('/browse/', defaults={'path': ''})
@shots.route('/browse/<path:path>',)
def shots_browse(path):
    path = os.path.join('/shots/browse/', path)
    print path
    path_data = json.loads(http_request(BRENDER_SERVER, path))
    return render_template('browse_modal.html',
        # items=path_data['items'],
        items_list=path_data['items_list'],
        parent_folder=path + '/..')


@shots.route('/delete', methods=['POST'])
def shots_delete():
    shot_ids = request.form['id']
    print(shot_ids)
    params = {'id': shot_ids}
    shots = http_request(BRENDER_SERVER, '/shots/delete', params)
    return 'done'


@shots.route('/update', methods=['POST'])
def shots_start():
    command = request.form['command'].lower()
    shot_ids = request.form['id']
    params = {'id': shot_ids}
    if command in ['start', 'stop', 'reset']:
        shots = http_request(BRENDER_SERVER,
            '/shots/%s' % (command), params)
        return shots
    else:
        return 'error'


@shots.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        shot_values = {
            'attract_shot_id': 1,
            'show_id': request.form['show_id'],
            'shot_name': request.form['shot_name'],
            'frame_start': request.form['frame_start'],
            'frame_end': request.form['frame_end'],
            'chunk_size': request.form['chunk_size'],
            'current_frame': request.form['frame_start'],
            'filepath': request.form['filepath'],
            'render_settings': request.form['render_settings'],
            'status': 'running',
            'priority': 10,
            'owner': 'fsiddi'
        }

        http_request(BRENDER_SERVER, '/shots/add', shot_values)

        #  flashing does not work because we use redirect_url
        #  flash('New shot added!')

        return redirect(url_for('shots.index'))
    else:
        render_settings = json.loads(http_request(BRENDER_SERVER, '/settings/render'))
        shows = json.loads(http_request(BRENDER_SERVER, '/shows/'))
        settings = json.loads(http_request(BRENDER_SERVER, '/settings/'))
        return render_template('shots/add_modal.html',
                            render_settings=render_settings,
                            settings=settings,
                            shows=shows)

