import json
import logging
from platform import system
from os.path import isfile
from os.path import join
from os import listdir

from flask import jsonify
from flask.ext.restful import Resource
from flask.ext.restful import reqparse

from application import db
from application.modules.settings.model import Setting

parser = reqparse.RequestParser()
parser.add_argument('blender_path_linux', type=str)
parser.add_argument('blender_path_win', type=str)
parser.add_argument('blender_path_osx', type=str)
parser.add_argument('render_settings_path_linux', type=str)
parser.add_argument('render_settings_path_win', type=str)
parser.add_argument('render_settings_path_osx', type=str)
parser.add_argument('group', type=str)

setting_parser = reqparse.RequestParser()
setting_parser.add_argument('value', type=str)


class SettingsListApi(Resource):
    def get(self):
        settings = Setting.query.all()
        ret = {}
        for setting in settings:
            try:
                val = json.loads(setting.value)
            except:
                val = setting.value
            ret[setting.name] = val
        return jsonify(**ret)

    def post(self):
        args = parser.parse_args()
        for k, v in args.iteritems():
            setting = Setting.query.filter_by(name=k).first()
            if setting:
                setting.value = v
                logging.info("Updating {0} {1}".format(k, v))
            else:
                setting = Setting(name=k, value=v)
                logging.info("Creating {0} {1}".format(k, v))
            db.session.add(setting)
        db.session.commit()
        return '', 204

class SettingApi(Resource):
    """API to edit individual settings.
    """
    def get(self, name):
        setting = Setting.query.filter_by(name=name).first()
        ret = {}
        if setting:
            ret = json.loads(setting.value)
        return jsonify(**ret)

    def patch(self, name):
        args = setting_parser.parse_args()
        value = args['value']
        setting = Setting.query.filter_by(name=name).first()
        if setting:
            setting.value = value
            logging.info("Updating {0} {1}".format(name, value))
        else:
            setting = Setting(name=name, value=value)
            logging.info("Creating {0} {1}".format(name, value))
        db.session.add(setting)
        db.session.commit()
        return jsonify(dict(value=setting.value))
