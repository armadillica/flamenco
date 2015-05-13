import json
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask import Blueprint
from flask import Response
from flask import jsonify
from flask import abort

from application import app
from application import http_server_request

# Name of the Blueprint
workers = Blueprint('workers', __name__)


@workers.route('/')
def index():
    return render_template('workers/index.html', title='workers')


@workers.route('/index.json')
def index_json():
    workers = http_server_request('get', '/workers')
    workers_list = []

    for key, val in workers.iteritems():
        val['checkbox'] = '<input type="checkbox" value="' + str(val['id']) + ';' + str(val['manager_id']) + '"/>'
        workers_list.append({
            "DT_RowId": "worker_" + str(val['id']),
            "checkbox": val['checkbox'],
            "hostname": key,
            "system": val['system'],
            "ip_address": val['ip_address'],
            "connection": val['connection'],
            "status": val['status'],
            "id": val['id'],
            "activity": val['activity'],
            "manager_id": val['manager_id'],
        })

    # For debugging, if we add the pretty arg to the get request, we get a pretty
    # printed version of the workers_list
    if request.args.get('pretty'):
        print request.args.get('pretty')
        if request.args.get('pretty') == 'true':
            return jsonify(data=workers_list)

    # Default json return
    workers_list = {'data': workers_list}
    content = u"{0}".format(json.dumps(workers_list))
    return Response(content, mimetype='application/json')


@workers.route('/edit', methods=['POST'])
def edit():
    worker_ids = request.form['id']
    worker_status = request.form['status'].lower()

    #worker_config = {'system': 'linux',
    #                'blender': 'local'}
    params = dict(id=worker_ids, status=worker_status)
                #'config': worker_config}
    r = http_server_request('post', '/workers', params)

    return jsonify(status=worker_status)


    #return redirect(url_for('workers.index'))


@workers.route('/view/<worker_id>')
def view(worker_id):
    worker = http_server_request('get', '/workers/{0}'.format(worker_id))
    return render_template('workers/view.html', worker=worker)

