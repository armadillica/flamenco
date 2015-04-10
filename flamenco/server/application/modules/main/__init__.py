import urllib
import logging
import json

from application.modules.managers.model import Manager
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
    return jsonify(message='Flamenco server up and running!')


@main.route('/connect', methods=['POST'])
def connect():
    # We assemble the remote_addr value with
    # the port value sent from the manager
    ip_address = request.remote_addr + ':' + str(request.form['port'])
    hostname = request.form['name']

    manager = Manager.query.filter_by(mac_address=mac_address).first()

    if manager:
        logging.info('Known manager requested connection, updating IP address')
        manager.ip_address = ip_address
        db.session.add(manager)
        db.session.commit()

    else:
        logging.info('New manager requested connection')
        # create new manager object with some defaults.
        # Later on most of these values will be passed as JSON object
        # during the first connection

        manager = Manager(name=hostname,
                          port=port,
                          ip_address=ip_address)

        db.session.add(manager)
        db.session.commit()
        logging.info('Manager added')

    # we verify the identity of the manager (will check on database)
    try:
        f = urllib.urlopen('http://' + ip_address)
        manager = json.loads(f.read())
        logging.info('Manager connected:')
        for k, v in manager.iteritems():
            logging.info('  {0}: {1}'.format(k, v))
        return 'You are now connected to the server'
    except:
        error = "server could not connect to manager with ip=" + ip_address
