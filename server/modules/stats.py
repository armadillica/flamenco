import json

from flask import Blueprint, render_template, abort, jsonify, request

from server.model import *
from server.utils import *

stats_module = Blueprint('stats_module', __name__)


@stats_module.route('/stats/')
def stats():
    # Here we will aget some basic statistics and infos from the server.
    stats = {
            "total_jobs":Jobs.select().count(),
            "total_shots":Shots.select().count(),
            "total_shows":Shows.select().count(),
            }

    #b = Jobs.select().count()


    return jsonify(server_stats=stats)
