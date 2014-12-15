import requests
from HTMLParser import HTMLParser
from flask import Flask
from flask import render_template
from flask import abort

app = Flask(__name__)

app.config.update(
    SECRET_KEY='A0Zr98j/3yX R~XHH!jmN]LWX/,?RT',
    DEBUG=False,
    HOST='localhost',
    PORT=8888,
    BRENDER_SERVER='localhost:9999'
)


def check_connection():
    try:
        http_server_request('get', '/')
        return "online"
    except:
        return "offline"

class ServerError(Exception):
    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        self.payload = payload

    def to_html(self):
        return HTMLParser().unescape(self.message).decode('utf8', 'ignore')

def server_check_error(response):
    if response.status_code == 500:
        s =""
        for chunk in response.iter_content(50):
            s += chunk
        raise ServerError(s)

def http_request(ip_address, method, post_params=False):
    """Utils function used to communicate with the server
    """
    if post_params:
        r = requests.post('http://' + ip_address + method, data=post_params)
    else:
        r = requests.get('http://' + ip_address + method)

    server_check_error(r)
    return r.json()

def http_server_request(method, path, params=None):
    """New version of the http_request function
    """

    if method == 'get':
        r = requests.get('http://' + app.config['BRENDER_SERVER'] + path)
    elif method == 'delete':
        r = requests.delete('http://' + app.config['BRENDER_SERVER'] + path, params)
    if method == 'post':
        r = requests.post('http://' + app.config['BRENDER_SERVER'] + path, params)
    if method == 'put':
        r = requests.put('http://' + app.config['BRENDER_SERVER'] + path, params)

    if r.status_code == 204:
        return '', 204

    if r.status_code == 404:
        return abort(404)

    server_check_error(r)
    return r.json()


def list_integers_string(string_list):
    """Accepts comma separated string list of integers
    """
    integers_list = string_list.split(',')
    integers_list = map(int, integers_list)
    return integers_list

from dashboard.controllers.main import main
from dashboard.controllers.jobs import jobs
from dashboard.controllers.workers import workers
from dashboard.controllers.settings import settings
from dashboard.controllers.projects import projects
from dashboard.controllers.render import render
app.register_blueprint(main)
app.register_blueprint(jobs, url_prefix='/jobs')
app.register_blueprint(workers, url_prefix='/workers')
app.register_blueprint(settings, url_prefix='/settings')
app.register_blueprint(projects, url_prefix='/projects')
app.register_blueprint(render, url_prefix='/render')

@app.errorhandler(404)
def page_not_found(error):
    return render_template('404_error.html'), 404

@app.errorhandler(ServerError)
def server_error(error):
    return render_template('500_error.html', error=error.to_html()), 500

def run(user_config=None):
    config = app.config

    if user_config:
        config.from_object(user_config)

    config.update(
        SERVER_NAME="%s:%s" % (config['HOST'], config['PORT'])
    )

    app.run(config['HOST'], config['PORT'])
