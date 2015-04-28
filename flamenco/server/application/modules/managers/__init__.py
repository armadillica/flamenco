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

parser = reqparse.RequestParser()
parser.add_argument('port', type=int)
parser.add_argument('name', type=str)
parser.add_argument('total_workers', type=int)
parser.add_argument('has_virtual_workers', type=int)


class ManagerListApi(Resource):
    def post(self):
        """Upon every manager startup, we check this resource to know if
        the manager already existed. If not, we create one and assign it a
        unique identifier.
        """
        args = parser.parse_args()
        ip_address = request.remote_addr
        port = args['port']
        has_virtual_workers = args['has_virtual_workers']

        manager = Manager.query\
            .filter_by(ip_address=ip_address)\
            .filter_by(port=port)\
            .first()

        if not manager:
            u = uuid.uuid1()
            manager = Manager(
                name=args['name'],
                ip_address=ip_address,
                port=port,
                has_virtual_workers=has_virtual_workers,
                uuid=u.hex)
            db.session.add(manager)
            db.session.commit()
            logging.info("New manager registered with uuid: {0}".format(u.hex))
        else:
            # Handle the case where the manager has no UUID
            if not manager.uuid:
                u = uuid.uuid1()
                manager.uuid = u.hex
                db.session.commit()
                logging.info("Manager updated with uuid: {0}".format(u.hex))

        logging.info("Manager connected at {0}:{1}".format(manager.ip_address, manager.port))

        return jsonify(uuid=manager.uuid)


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
                "port" : manager.port,
                "connection" : 'online',
                "uuid": manager.uuid
            }
        return jsonify(managers)


class ManagerApi(Resource):
    def get(self, manager_uuid):
        try:
            manager = Manager.query.filter_by(uuid=manager_uuid).one()
        except NoResultFound:
            logging.warning("No manager found in Database")
            return '', 404
        manager_dict = {
            'id': manager.id,
            'ip_address': manager.ip_address,
            'port': manager.port,
            'uuid': manager.uuid,
        }
        url = 'http://' + manager.ip_address+':'+str(manager.port)+'/settings'
        try:
            r = requests.get(url)
            manager_dict['settings'] = r.text
        except ConnectionError:
            logging.error(
                'Can not connect with the Manager {0}'.format(manager.uuid))
        return jsonify(manager_dict)

    def patch(self, manager_uuid):
        from application.modules.tasks import TaskApi

        args = parser.parse_args()
        try:
            manager = Manager.query.filter_by(uuid=manager_uuid).one()
        except NoResultFound:
            logging.warning("No manager found in Database")
            return '', 404

        # TODO add try except statement to safely handle .one() query
        manager.total_workers = args['total_workers']
        db.session.add(manager)
        db.session.commit()
        TaskApi.dispatch_tasks()
        return jsonify(dict(total_workers=manager.total_workers))
