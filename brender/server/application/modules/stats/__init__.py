from flask import Blueprint, jsonify
from application.modules.tasks.model import Task
from application.modules.jobs.model import Job
from application.modules.projects.model import Project

from application import db

stats = Blueprint('stats', __name__)


@stats.route('/')
def index():
    # Here we will get some basic statistics and infos from the server.
    stats = {
            "total_jobs":Task.query.count(),
            "total_shots":Job.query.count(),
            "total_projects":Project.query.count(),
            }

    return jsonify(server_stats=stats)
