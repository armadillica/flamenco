from flask import Blueprint, jsonify
from server.model import Job, Shot, Show

from server import db

stats = Blueprint('stats', __name__)


@stats.route('/')
def index():
    # Here we will get some basic statistics and infos from the server.
    stats = {
            "total_jobs":Job.query.count(),
            "total_shots":Shot.query.count(),
            "total_shows":Show.query.count(),
            }

    return jsonify(server_stats=stats)
