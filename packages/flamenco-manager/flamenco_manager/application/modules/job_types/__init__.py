import json
import logging

from flask import jsonify
from flask import abort
from flask.ext.restful import Resource
from flask.ext.restful import reqparse

from application import db
from application.modules.job_types.model import JobType

job_type_parser = reqparse.RequestParser()
job_type_parser.add_argument('name', type=str)
job_type_parser.add_argument('properties', type=str)


class JobTypeListApi(Resource):
    def get(self):
        """Return the list of available job types."""
        ret = []
        for job_type in JobType.query.all():
            try:
                job = json.loads(job_type.properties)
            except:
                job = {}
            job['id'] = job_type.id
            job['name'] = job_type.name
            ret.append(job)
        return jsonify(items=ret)

    # TODO: add post function to allow creation of new Job Types.


class JobTypeApi(Resource):
    """API to manage a Job Type. Currelty we query for a Job Type using its name.
    We should probably use ids, but names are more descriptive.
    """
    def get(self, name):
        job_type = JobType.query.filter_by(name=name).first()
        ret = {}
        if job_type:
            ret = json.loads(job_type.properties)
        return jsonify(**ret)

    def patch(self, name):
        args = job_type_parser.parse_args()
        properties = args['properties']
        job_type = JobType.query.filter_by(name=name).first()
        if job_type:
            job_type.properties = properties
            db.session.commit()
            logging.info("Updating {0} {1}".format(name, properties))
        else:
            return abort(404)
        return jsonify(dict(properties=job_type.properties))


def get_job_type_paths(job_type_name, worker):
    job_paths = JobType.query.filter_by(name=job_type_name).one()
    paths = json.loads(job_paths.properties)
    worker_system = worker.system.split()[0]
    for k, v in paths.items():
        paths[k] = v[worker_system]
    return paths
