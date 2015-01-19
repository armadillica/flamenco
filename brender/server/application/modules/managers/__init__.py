import logging

from flask import request
from flask import jsonify
from flask.ext.restful import Resource
from flask.ext.restful import reqparse

from application import db
from application import app

from application.modules.managers.model import Manager

parser = reqparse.RequestParser()
parser.add_argument('port', type=int)
parser.add_argument('name', type=str)

class ManagersApi(Resource):
    def post(self):
        args = parser.parse_args()
        ip_address = request.remote_addr
        port = args['port']

        manager = Manager.query\
            .filter_by(ip_address=ip_address)\
            .filter_by(port=port)\
            .first()

        if not manager:
            manager = Manager(name=args['name'],
                ip_address=ip_address,
                port=port)
            db.session.add(manager)
            db.session.commit()

        logging.info("Manager connected at {0}:{1}".format(manager.ip_address, manager.port))

        return '', 204


    def get(self):
        managers={}
        for manager in Manager.query.all():
            manager.connection = 'online' if manager.is_connected else 'offline'
            managers[manager.name] = {
                "id" : manager.id,
                "name" : manager.name,
                "ip_address" : manager.ip_address,
                "port" : manager.port
            }
        return jsonify(managers)
