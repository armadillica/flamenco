import json

from flask import Blueprint, render_template, abort, jsonify, request

from model import *
from utils import *

stats_module = Blueprint('stats_module', __name__)


@stats_module.route('/stats/')
def stats():
    # Here we will aget some basic statistics and infos from the server.
    stats = {
        "total_jobs":Jobs.select().naive().count(),
        "total_shots":Shots.select().naive().count(),
        "total_shows":Shows.select().naive().count(),
        "total_workers":Workers.select().naive().count(),
        "currently_connected_workers":Workers.select().where(Workers.connection == 'online').naive().count(),
        "currently_disconnected_workers":Workers.select().where(Workers.connection == 'offline').naive().count()
    }

    #b = Jobs.select().count()


    return jsonify(server_stats=stats)
