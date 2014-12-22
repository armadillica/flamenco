from flask.ext.restful import Resource
from flask.ext.restful import reqparse
from flask import request
from application.modules.managers.model import Manager
from flask import jsonify

from application import db
from application import app

parser = reqparse.RequestParser()
parser.add_argument('port', type=int)
parser.add_argument('name', type=str)

class ManagersApi(Resource):
    def post(self):
        args = parser.parse_args()
        ip_address = request.remote_addr
        port = args['port']

        # TODO replace by db query
        #manager = Manager.query.filter_by(ip_address=ip_address,port=port).first()
        manager_list = filter(lambda m : m.ip_address == ip_address and m.port == port, app.config['MANAGERS'])
        manager = None if manager_list is [] else manager_list[0]
        if not manager:
            manager = Manager(name=args['name'],
                          ip_address=ip_address,
                          port=port)

            app.config['MANAGERS'].append(manager)


            #db.session.add(manager)
            #db.session.commit()

        print "Manager connected at %s:%d" % (manager.ip_address, manager.port)

        return '', 204


    def get(self):
        managers={}
        # TODO replace by db query
        managers_db = app.config['MANAGERS']
        for manager in managers_db:
            manager.connection = 'online' if manager.is_connected else 'offline'
            #db.session.add(manager)

            managers[manager.name] = {"id": manager.id,
                                        "name": manager.name,
                                        "ip_address": manager.ip_address,
                                        "port":manager.port}
        #db.session.commit()
        return jsonify(managers)
