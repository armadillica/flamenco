import json

import os
from os import listdir
from os.path import isfile, join, abspath, dirname
from flask import Blueprint, render_template, abort, jsonify, request

from server.model import *
from server.utils import *

from server import db

settings = Blueprint('settings', __name__)


@settings.route('/')
def index():
    settings = {}
    for setting in Setting.query.all():
        settings[setting.name] = setting.value

    return jsonify(settings)


@settings.route('/update', methods=['POST'])
def settings_update():
    for setting_name in request.form:
        setting = Setting.query.filter_by(name = setting_name).first()
        if setting:
            setting.value = request.form[setting_name]
            print('[Debug] Updating %s %s') % \
            (setting_name, request.form[setting_name])
        else:
            setting = Setting(
                name=setting_name,
                value=request.form[setting_name])
            print('[Debug] Creating %s %s') % \
            (setting_name, request.form[setting_name])
        db.session.add(setting)
        db.session.commit()
    return jsonify(reponse='updated')



@settings.route('/<setting_name>')
def get_setting(setting_name):
    setting = Setting.query.filter_by(name = setting_name)
    if setting:
        print('[Debug] Get Settings %s %s') % (setting.name, setting.value)
        return setting
    else:
        reponse = 'Setting %s not found' % setting_name
        return jsonify(response = response)


@settings.route('/render')
def render_settings():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    render_settings_path = os.path.join(path, 'render_settings/')
    onlyfiles = [f for f in listdir(render_settings_path) if isfile(join(render_settings_path, f))]
    #return str(onlyfiles)

    # Fix for OSX creating .DS_Store in Folders this just pops the item from
    # the array it doesnt actually delete the file
    for x in onlyfiles:
      if x == '.DS_Store':
        index = onlyfiles.index(x)
        onlyfiles.pop(index)

    settings_files = dict(
        settings_files=onlyfiles)

    return jsonify(settings_files)

@settings.route('/render/<sname>', methods=['GET', 'POST'])
def render_settings_edit(sname):
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    render_settings_path = os.path.join(path, 'render_settings/', sname)
    if not os.path.exists(render_settings_path):
        return jsonify(dict(filename=sname, content="file were not fonud"))
    if not os.path.isfile(render_settings_path):
        return jsonify(dict(filename=sname, content="file were not fonud"))

    if request.method == 'GET':
        f = open(render_settings_path, 'r')
        text = str(f.read())
        f.close()
        return jsonify(dict(text=text))
    elif request.method == 'POST':
        content = request.form['text']
        print content
        f = open(render_settings_path, 'w')
        f.write(content)
        f.close()
        return jsonify(message='done')

@settings.route('/render/add/', methods=['GET', 'POST'])
def render_settings_add():
    filename = request.form['filename']
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    render_settings_path = os.path.join(path, 'render_settings/', filename)
    print filename
    f = open(render_settings_path, 'w')
    f.close()
    return jsonify(message='done')
