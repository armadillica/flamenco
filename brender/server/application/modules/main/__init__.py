import urllib
import logging
import json

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
        logging.info('Known worker requested connection, updating IP address')
        worker.ip_address = ip_address
        db.session.add(worker)
        db.session.commit()

    else:
        logging.info('New worker requested connection')
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
        logging.info('Worker added')

    #params = urllib.urlencode({'worker': 1, 'eggs': 2})

    # we verify the identity of the worker (will check on database)
    try:
        f = urllib.urlopen('http://' + ip_address)
        worker = json.loads(f.read())
        logging.info('Worker connected:')
        for k, v in worker.iteritems():
            logging.info('  {0}: {1}'.format(k, v))
        return 'You are now connected to the server'
    except:
        error = "server could not connect to worker with ip=" + ip_address
