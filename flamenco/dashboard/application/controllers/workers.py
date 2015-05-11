import json
from flask import (redirect,
                   render_template,
                   request,
                   url_for,
                   Blueprint)

from application import app
from application import http_server_request

# Name of the Blueprint
workers = Blueprint('workers', __name__)


@workers.route('/')
def index():
    workers = http_server_request('get', '/workers')
    workers_list = []

    for key, val in workers.iteritems():
        val['checkbox'] = '<input type="checkbox" value="' + str(val['id']) + ';' + str(val['manager_id']) + '"/>'
        workers_list.append({
            "DT_RowId": "worker_" + str(val['id']),
            "0": val['checkbox'],
            "1": key,
            "2": val['system'],
            "3": val['ip_address'],
            "4": val['connection'],
            "5": val['status'],
            "6": val['id'],
            "7": val['activity'],
            "8": val['manager_id'],
        })

    entries = json.dumps(workers_list)

    return render_template('workers/index.html', entries=entries, title='workers')


@workers.route('/edit', methods=['POST'])
def edit():
    worker_ids = request.form['id']
    worker_status = request.form['status'].lower()

    #worker_config = {'system': 'linux',
    #                'blender': 'local'}
    params = dict(id=worker_ids, status=worker_status)
                #'config': worker_config}
    http_server_request('post', '/workers', params)

    return redirect(url_for('workers.index'))


@workers.route('/view/<worker_id>')
def view(worker_id):
    worker = http_server_request('get', '/workers/{0}'.format(worker_id))
    return render_template('workers/view.html', worker=worker)

