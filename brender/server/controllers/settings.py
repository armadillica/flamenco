import json

import os
from os import listdir
from os.path import isfile, join, abspath, dirname
from flask import Blueprint, render_template, abort, jsonify, request

from server.model import *
from server.utils import *

settings = Blueprint('settings', __name__)


@settings.route('/')
def index():
    settings = {}
    for setting in Settings.select():
        settings[setting.name] = setting.value
   
    return jsonify(settings)


@settings.route('/update', methods=['POST'])
def settings_update():
    for setting_name in request.form:
        try:
            setting = Settings.get(Settings.name == setting_name)
            setting.value = request.form[setting_name]
            setting.save()
            print('[Debug] Updating %s %s') % \
            (setting_name, request.form[setting_name])
        except Settings.DoesNotExist:
            setting = Settings.create(
                name=setting_name,
                value=request.form[setting_name])
            setting.save()
            print('[Debug] Creating %s %s') % \
            (setting_name, request.form[setting_name])
    return 'done'



@settings.route('/<setting_name>')
def get_setting(setting_name):
    try:
        setting = Settings.get(Settings.name == setting_name)
        print('[Debug] Get Settings %s %s') % (setting.name, setting.value)
    except Exception, e:
        print(e, '--> Setting not found')
        return 'Setting %s not found' % setting_name

    # a = json.loads(setting['value'])
    # print(a)

    return setting.value


@settings.route('/render')
def render_settings():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    render_settings_path = os.path.join(path, 'render_settings/')
    onlyfiles = [f for f in listdir(render_settings_path) if isfile(join(render_settings_path, f))]
    #return str(onlyfiles)
    settings_files = dict(
        settings_files=onlyfiles)

    return jsonify(settings_files)
