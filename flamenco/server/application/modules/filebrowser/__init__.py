from flask.ext.restful import Resource

from flask import jsonify
from flask import abort
import os
from os import listdir
from os.path import join
from os.path import exists

from application.modules.settings.model import Setting
from application.modules.projects.model import Project


class FileBrowserApi(Resource):
    @staticmethod
    def browse(path):
        """We browse the project folder on the server.
        The path value gets appended to the active_project path value. The result is returned
        in JSON format.
        """

        active_project = Setting.query.filter_by(name = 'active_project').first()
        active_project = Project.query.get(active_project.value)

        # path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        # render_settings_path = os.path.join(path, 'render_settings/')

        absolute_path_root = active_project.path_server
        parent_path = ''

        if path != '':
            absolute_path_root = os.path.join(absolute_path_root, path)
            parent_path = path + "/" + os.pardir

        # print(active_project.path_server)
        # print(listdir(active_project.path_server))

        # items = {}
        items_list = []

        if not os.path.isdir(absolute_path_root):
            return abort(404)

        for f in listdir(absolute_path_root):
            relative_path = os.path.join(path, f)
            absolute_path = os.path.join(absolute_path_root, f)

            # we are going to pick up only blend files and folders
            if absolute_path.endswith('blend'):
                # items[f] = relative_path
                items_list.append((f, relative_path, 'blendfile'))
            elif os.path.isdir(absolute_path):
                items_list.append((f, relative_path, 'folder'))

        #return str(onlyfiles)
        project_files = dict(
            project_path_server=active_project.path_server,
            parent_path=parent_path,
            # items=items,
            items_list=items_list)

        return project_files

    def get(self, path):
        return jsonify(self.browse(path))

class FileBrowserRootApi(Resource):
    def get(self):
        return jsonify(FileBrowserApi.browse(''))
