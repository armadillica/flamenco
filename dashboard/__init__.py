from flask import Flask

app = Flask(__name__)

app.config.update(
    SECRET_KEY='A0Zr98j/3yX R~XHH!jmN]LWX/,?RT',
    DEBUG=True,
    SERVER_NAME='brender-flask:8888'
)

from dashboard import controllers
