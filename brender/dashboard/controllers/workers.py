import json
import urllib
from flask import (flash,
                   jsonify,
                   redirect,
                   render_template,
                   request,
                   url_for,
                   make_response,
                   Blueprint)

from dashboard import app
from dashboard import list_integers_string
from dashboard import http_server_request

BRENDER_SERVER = app.config['BRENDER_SERVER']

# Name of the Blueprint
workers = Blueprint('workers', __name__)


@workers.route('/')
def index():
    workers = http_server_request('get', '/workers')
    workers_list = []

    for key, val in workers.iteritems():
        val['checkbox'] = '<input type="checkbox" value="' + str(val['id']) + '"/>'
        workers_list.append({
            "DT_RowId": "worker_" + str(val['id']),
            "0": val['checkbox'],
            "1": key,
            "2": val['system'],
            "3": val['ip_address'],
            "4": val['connection'],
            "5": val['status']
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
    #print(workers)
    worker = None
    try:
        workers = http_server_request('get', '/workers')
    except KeyError:
        '''
            there are multiple exceptions that we can use here

            1. KeyError
            2. UnboundLocalError
            3. NameError
            '''
        print 'worker does not exist'

    if worker_id in workers:
        for key, val in workers.iteritems():
            if worker_id in key:
                try:
                    worker = http_request(val['ip_address'], '/run_info')
                    entry = ({"ip_address": val['ip_address'], "worker_id": worker_id, "status": val['status']})
                    worker.update(entry)
                except IOError:
                    worker = {
                        'worker_id': worker_id,
                        'status': val['status'],
                        'update_frequent': {
                            'load_average': {
                                '5min': 'N/A',
                                '1min': 'N/A',
                                '15min': 'N/A'
                            },
                        },
                        'update_less_frequent': {
                            'worker_architecture': 'N/A',
                            'worker_mem_percent': 'N/A',
                            'worker_disk_percent': 'N/A',
                            'worker_cpu_percent': 'N/A',
                            'worker_num_cpus': 'N/A',
                        },
                        'hostname': 'N/A',
                        'system': 'N/A',
                        'mac_address': 'N/A',
                        # 'worker_blender_cpu_usage': 'N/A',
                        # 'worker_blender_mem_usage': 'N/A'
                    }

    if worker:
        return render_template('workers/view.html', worker=worker)
    else:
        return make_response('worker ' + worker_id + ' doesnt exist')
