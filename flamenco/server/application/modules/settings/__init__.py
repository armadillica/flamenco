import logging
import requests
from platform import system
from os.path import isfile
from os.path import join
from os import listdir

from flask import jsonify
from flask.ext.restful import Resource
from flask.ext.restful import fields
from flask.ext.restful import marshal_with
from flask.ext.restful import reqparse

from application import db
from application.modules.settings.model import Setting
from application.modules.managers.model import Manager

from requests.exceptions import ConnectionError

parser = reqparse.RequestParser()
parser.add_argument('blender_path_linux', type=str)
parser.add_argument('blender_path_win', type=str)
parser.add_argument('blender_path_osx', type=str)
parser.add_argument('render_settings_path_linux', type=str)
parser.add_argument('render_settings_path_win', type=str)
parser.add_argument('render_settings_path_osx', type=str)
parser.add_argument('active_project', type=str)

parser_settings = reqparse.RequestParser()
parser_settings.add_argument('value', type=str)

class SettingsListApi(Resource):
    def get(self):
        settings = {}
        settings['settings'] = []
        for setting in Setting.query.all():
            settings['settings'].append( {
                'name': setting.name,
                'value': setting.value
            })

        return jsonify(**settings)

    def post(self):
        args = parser.parse_args()
        for k, v in args.iteritems():
            setting = Setting.query.filter_by(name = k).first()
            if setting:
                setting.value = v
                logging.info("Updating {0} {1}".format(k, v))
            else:
                setting = Setting(name=k, value=v)
                logging.info("Creating {0} {1}".format(k, v))
            db.session.add(setting)
        db.session.commit()
        return '', 204

class ManagersSettingsApi(Resource):
    def get(self):
        managers = Manager.query.all()
        managers_settings = {}
        for manager in managers:
            if manager.host:
                if manager.has_virtual_workers:
                    continue
                r = None
                try:
                    r = requests.get(manager.host)
                except ConnectionError:
                    logging.error(
                        'Cant connect with manager {0}'.format(
                            manager.host))
                if r:
                    managers_settings[manager.id] = r.json()
                    managers_settings[manager.id]['manager_name']=manager.name
        return jsonify(managers_settings)

class ManagerSettingApi(Resource):
    def post(self, manager_id, setting_name):
        args = parser_settings.parse_args()
        print ("Updating {0} in {1}".format(setting_name, manager_id))
        manager = Manager.query.get(manager_id)
        url = 'http://{0}:{1}/settings/{2}'.format(
            manager.ip_address, manager.port, setting_name)
        data = {'value': args['value']}
        requests.patch(url, data=data, timeout=20)

        return '', 200
