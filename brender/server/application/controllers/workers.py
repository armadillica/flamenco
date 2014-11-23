from flask import Blueprint, render_template, abort, jsonify, request

from application.model import Worker
from application.utils import *

from application import db

workers = Blueprint('workers', __name__)


def update_worker(worker, worker_data):
    if worker.connection != 'offline':
        worker.connection = 'online'
        db.session.add(worker)
        db.session.commit()
        http_request(worker.ip_address, '/update', worker_data)


    for key, val in worker_data.iteritems():
        print(key, val)
        if val:
            setattr(worker, key, val)
    db.session.add(worker)
    db.session.commit()
    print('status ', worker.status)


@workers.route('/')
def index():
    workers = {}

    for worker in Worker.query.all():
        try:
            f = urllib.urlopen('http://' + worker.ip_address)
            worker.connection = 'online'
        except Exception, e:
            print('[Warning] Worker', worker.hostname, 'is not online')
            worker.connection = 'offline'

        workers[worker.hostname] = {"id": worker.id,
                                    "hostname": worker.hostname,
                                    "status": worker.status,
                                    "connection": worker.connection,
                                    "system": worker.system,
                                    "ip_address": worker.ip_address}

    """
    This is a temporary solution for saving the workers connections:
    we read them from the workers dict we just created and build an
    update query for each one of them. It seems not possible to save
    the objects on the fly in the Workers.select() loop above.
    """

    for k, v in workers.iteritems():
        worker = Worker.query.get(v['id'])
        worker.connection = v['connection']
        db.session.add(worker)
        db.session.commit()

    return jsonify(workers)

@workers.route('/update', methods=['POST'])
def workers_update():
    status = request.form['status']
    # TODO parse
    workers_ids = request.form['id']
    workers_list = list_integers_string(workers_ids)
    for worker_id in workers_list:
        print("updating worker %s = %s " % (worker_id, status))
    return jsonify(status='done')


@workers.route('/edit', methods=['POST'])
def workers_edit():
    worker_ids = request.form['id']
    worker_data = {"status": request.form['status'],
                   "config": request.form['config']}

    if worker_ids:
        for worker_id in list_integers_string(worker_ids):
            worker = Worker.query.get(worker_id)
            update_worker(worker, worker_data)

        return jsonify(result='success')
    else:
        print('we edit all the workers')
        for worker in Workers.select():
            update_worker(worker, worker_data)

    return jsonify(result='success')

