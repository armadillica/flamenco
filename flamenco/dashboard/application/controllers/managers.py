import json
from flask import (redirect,
                   render_template,
                   request,
                   url_for,
                   Blueprint)

from application import app
from application import http_server_request

BRENDER_SERVER = app.config['BRENDER_SERVER']

# Name of the Blueprint
managers = Blueprint('managers', __name__)


@managers.route('/')
def index():
    managers = http_server_request('get', '/managers')
    managers_list = []

    for key in managers:
        val = managers[key]
        val['checkbox'] = '<input type="checkbox" value="' \
            + str(val['id']) + ';' + str(val['id']) + '"/>'
        managers_list.append({
            "DT_RowId": "manager_" + str(val['id']),
            "0": val['checkbox'],
            "1": key,
            "2": val['uuid'],
            "3": val['ip_address'],
            "4": val['port'],
            "5": val['connection'],
            "6": val['id'],
        })

    entries = json.dumps(managers_list)

    return render_template('managers/index.html',
                           entries=entries,
                           title='managers')


@managers.route('/edit', methods=['POST'])
def edit():
    worker_ids = request.form['id']
    worker_status = request.form['status'].lower()

    #worker_config = {'system': 'linux',
    #                'blender': 'local'}
    params = dict(id=worker_ids, status=worker_status)
                #'config': worker_config}
    http_server_request('post', '/managers', params)

    return redirect(url_for('managers.index'))


@managers.route('/view/<manager_id>')
def view(manager_id):
    manager = http_server_request('get', '/managers/{0}'.format(manager_id))
    return render_template('managers/view.html', manager=manager)

