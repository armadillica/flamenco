import urllib

from application.modules.workers.model import Worker
from application import db
from flask import Flask
from flask import Blueprint
from flask import render_template
from flask import jsonify
from flask import redirect
from flask import url_for
from flask import request

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return jsonify(message='Brender server up and running!')


@main.route('/connect', methods=['POST'])
def connect():
    # We assemble the remote_addr value with
    # the port value sent from the worker
    ip_address = request.remote_addr + ':' + str(request.form['port'])
    mac_address = request.form['mac_address']
    hostname = request.form['hostname']
    system = request.form['system']

    worker = Worker.query.filter_by(mac_address=mac_address).first()

    if worker:
        print('This worker connected before, updating IP address')
        worker.ip_address = ip_address
        db.session.add(worker)
        db.session.commit()

    else:
        print('This worker never connected before')
        # create new worker object with some defaults.
        # Later on most of these values will be passed as JSON object
        # during the first connection

        worker = Worker(hostname=hostname,
                        mac_address=mac_address,
                        status='enabled',
                        connection='online',
                        warning=False,
                        config='{}',
                        system=system,
                        ip_address=ip_address)

        db.session.add(worker)
        db.session.commit()

        print('Worker has been added')

    #params = urllib.urlencode({'worker': 1, 'eggs': 2})

    # we verify the identity of the worker (will check on database)
    try:
        f = urllib.urlopen('http://' + ip_address)
        print('The following worker just connected:')
        print(f.read())
        return 'You are now connected to the server'
    except:
        error = "server could not connect to worker with ip=" + ip_address
