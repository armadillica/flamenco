import json

from os import listdir
from os.path import isfile, join

from flask import Blueprint, render_template, abort, jsonify, request

from model import *
from utils import *

settings_module = Blueprint('settings_module', __name__)


@settings_module.route('/settings/')
def settings():
    settings = {}
    for setting in Settings.select():
        settings[setting.name] = setting.value
    return jsonify(settings)


@settings_module.route('/settings/update', methods=['POST', 'GET'])
def settings_update():
    if request.method == 'POST':
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
    else:
        return 'This is a useless GET'


@settings_module.route('/settings/<setting_name>')
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


@settings_module.route('/render-settings/')
def render_settings():
    render_settings_path = './render_settings/'
    onlyfiles = [ f for f in listdir(render_settings_path) if isfile(join(render_settings_path,f)) ]
    onlyfiles = [f for f in listdir(render_settings_path) if isfile(join(render_settings_path, f))]
    #return str(onlyfiles)
    settings_files = dict(
        settings_files=onlyfiles)

    return jsonify(settings_files)
