import json

from flask import Blueprint, render_template, abort, jsonify, request

from server.model import *
from server.utils import *

stats = Blueprint('stats', __name__)


@stats.route('/')
def index():
    # Here we will aget some basic statistics and infos from the server.
    stats = {
            "total_jobs":Jobs.select().count(),
            "total_shots":Shots.select().count(),
            "total_shows":Shows.select().count(),
            }

    #b = Jobs.select().count()


    return jsonify(server_stats=stats)
