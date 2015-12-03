import logging
import uuid
import requests
from flask import request
from flask import jsonify
from flask.ext.restful import Resource
from flask.ext.restful import reqparse

from application import db
from application import app

from flask.ext.restful import marshal_with
from flask.ext.restful import fields
from application.utils import list_integers_string

from application.modules.managers.model import Manager

from requests.exceptions import ConnectionError

parser_manager = reqparse.RequestParser()
parser_manager.add_argument('host', type=str)
parser_manager.add_argument('port', type=int)
parser_manager.add_argument('name', type=str)
parser_manager.add_argument('token', type=str)
parser_manager.add_argument('total_workers', type=int)
parser_manager.add_argument('has_virtual_workers', type=int)


class ManagerListApi(Resource):
    def post(self):
        """Upon every manager startup, we check this resource to know if
        the manager already existed. If not, we create one and assign it a
        unique identifier.
        """
        args = parser_manager.parse_args()
        ip_address = request.remote_addr
        token = args['token']
        has_virtual_workers = args['has_virtual_workers']

        if token:
            manager = Manager.query\
                .filter_by(token=token)\
                .first()
            if manager:
                token = uuid.uuid1()
                manager.token = token.hex
                db.session.commit()
                logging.info("Manager token updated: {0}".format(token.hex))
            else:
                return '', 404
        else:
            token = uuid.uuid1()
            manager = Manager(
                name=args['name'],
                ip_address=ip_address,
                has_virtual_workers=has_virtual_workers,
                host="http://{0}:{1}".format(ip_address, args['port']),
                token=token.hex)
            db.session.add(manager)
            db.session.commit()
            logging.info("New manager registered with uuid: {0}".format(token.hex))


        logging.info("Manager connected at {0}".format(manager.ip_address))

        return jsonify(token=manager.token)


    def get(self):
        managers={}
        for manager in Manager.query.all():
            # We check if the manager is connected by actually attempting a connection
            #manager.connection = 'online' if manager.is_connected else 'offline'
            # TODO: possibly update count of total_workers
            managers[manager.name] = {
                "id" : manager.id,
                "name" : manager.name,
                "ip_address" : manager.ip_address,
                "host" : manager.host,
                "connection" : 'online',
                "token": manager.token
            }
        return jsonify(managers)


class ManagerApi(Resource):
    def get(self, manager_id):
        manager = Manager.query.get_or_404(manager_id)

        manager_dict = {
            'id': manager.id,
            'ip_address': manager.ip_address,
            'host': manager.host,
            'token': manager.token,
        }
        url = manager.host + '/settings'
        try:
            r = requests.get(url)
            manager_dict['settings'] = r.text
        except ConnectionError:
            logging.error(
                'Can not connect with the Manager {0}'.format(manager.host))
        return jsonify(manager_dict)

    def patch(self, manager_id):
        from application.modules.tasks import TaskApi

        args = parser_manager.parse_args()
        manager = Manager.query.get_or_404(manager_id)

        # TODO add try except statement to safely handle .one() query
        manager.total_workers = args['total_workers']
        db.session.add(manager)
        db.session.commit()
        TaskApi.dispatch_tasks()
        return jsonify(dict(total_workers=manager.total_workers))
