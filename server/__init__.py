import urllib
import time

from flask import Flask, render_template, jsonify, redirect, url_for, request
from model import *
from modules.jobs import jobs_module
from modules.workers import workers_module
from modules.shots import shots_module
from modules.shows import shows_module
from modules.settings import settings_module
from modules.stats import stats_module

app = Flask(__name__)
app.config.update(
    DEBUG=True,
    SERVER_NAME='brender-server:9999'
)

from server import controllers

app.register_blueprint(workers_module)
app.register_blueprint(jobs_module)
app.register_blueprint(shots_module)
app.register_blueprint(shows_module)
app.register_blueprint(settings_module)
app.register_blueprint(stats_module)