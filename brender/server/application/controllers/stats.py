from flask import Blueprint, jsonify
from application.model import Job
from application.model import Shot
from application.modules.projects.model import Project

from application import db

stats = Blueprint('stats', __name__)


@stats.route('/')
def index():
    # Here we will get some basic statistics and infos from the server.
    stats = {
            "total_jobs":Job.query.count(),
            "total_shots":Shot.query.count(),
            "total_projects":Project.query.count(),
            }

    return jsonify(server_stats=stats)
