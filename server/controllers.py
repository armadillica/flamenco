from model import *

from modules.jobs import jobs_module
from modules.workers import workers_module
from modules.shots import shots_module
from modules.shows import shows_module
from modules.settings import settings_module
from modules.stats import stats_module
from flask import Flask, render_template, jsonify, redirect, url_for, request

app = Flask(__name__)

@app.route('/')
def index():
    #add_random_workers(2)
    return jsonify(status='ok')


@app.route('/connect', methods=['POST', 'GET'])
def connect():
    error = None
    if request.method == 'POST':
        #return str(request.json['foo'])

        #ip_address = request.form['ip_address']

        # We assemble the remote_addr value with
        # the port value sent from the worker
        ip_address = request.remote_addr + ':' + str(request.form['port'])
        mac_address = request.form['mac_address']
        hostname = request.form['hostname']
        system = request.form['system']

        try:
            worker = Workers.get(Workers.mac_address == mac_address)
        except Exception, e:
            print(e, '--> Worker not found')
            worker = None

        if worker:
            print('This worker connected before, updating IP address')
            worker.ip_address = ip_address
            worker.save()

        else:
            print('This worker never connected before')
            # create new worker object with some defaults.
            # Later on most of these values will be passed as JSON object
            # during the first connection

            worker = Workers.create(hostname=hostname,
                                    mac_address=mac_address,
                                    status='enabled',
                                    connection='online',
                                    warning=False,
                                    config='{}',
                                    system=system,
                                    ip_address=ip_address)

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

    # the code below is executed if the request method
    # was GET or the credentials were invalid
    return jsonify(error=error)

app.register_blueprint(workers_module)
app.register_blueprint(jobs_module)
app.register_blueprint(shots_module)
app.register_blueprint(shows_module)
app.register_blueprint(settings_module)
app.register_blueprint(stats_module)
