import urllib
from flask import Flask

app = Flask(__name__)

app.config.update(
    SECRET_KEY='A0Zr98j/3yX R~XHH!jmN]LWX/,?RT',
    DEBUG=False,
    HOST='localhost',
    PORT=8888,
    BRENDER_SERVER='localhost:9999'
)


def check_connection(host_address):
    try:
        http_request(host_address, '/')
        return "online"
    except:
        return "offline"


def http_request(ip_address, method, post_params=False):
    """Utils function used to communicate with the serve
    """
    # post_params must be a dictionnary
    if post_params:
        params = urllib.urlencode(post_params)
        f = urllib.urlopen('http://' + ip_address + method, params)
    else:
        f = urllib.urlopen('http://' + ip_address + method)

    print('message sent, reply follows:')
    return f.read()


def list_integers_string(string_list):
    """Accepts comma separated string list of integers
    """
    integers_list = string_list.split(',')
    integers_list = map(int, integers_list)
    return integers_list

from dashboard.controllers.main import main
from dashboard.controllers.shots import shots
from dashboard.controllers.workers import workers
from dashboard.controllers.settings import settings
from dashboard.controllers.shows import shows
app.register_blueprint(main)
app.register_blueprint(shots, url_prefix='/shots')
app.register_blueprint(workers, url_prefix='/workers')
app.register_blueprint(settings, url_prefix='/settings')
app.register_blueprint(shows, url_prefix='/shows')


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404_error.html'), 404


def run(user_config=None):
    config = app.config

    if user_config:
        config.from_object(user_config)

    config.update(
        SERVER_NAME="%s:%s" % (config['HOST'], config['PORT'])
    )

    app.run(config['HOST'], config['PORT'])
