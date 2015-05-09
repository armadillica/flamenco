# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Flamenco Integration",
    "author": "Eibriel",
    "version": (0, 5),
    "blender": (2, 73, 0),
    "location": "View3D > Tool Shelf > Flamenco",
    "description": "BAM pack current file \
        and send it to the Flamenco Renderfarm",
    "warning": "Warning!",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Render"}

import bpy
import os
import json
import requests
import subprocess
# from time import strftime

from bpy.props import IntProperty
from bpy.props import BoolProperty
from bpy.props import StringProperty
from bpy.props import EnumProperty
from bpy.props import CollectionProperty

from requests.exceptions import ConnectionError
from requests.exceptions import Timeout

from bpy.types import AddonPreferences


class flamencoPreferences(AddonPreferences):
    bl_idname = __name__

    flamenco_server = StringProperty(
        name="Flamenco Server URL",
        default="http://127.0.0.1:9999",
        options={'HIDDEN', 'SKIP_SAVE'})

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "flamenco_server")


class flamencoUpdate (bpy.types.Operator):
    """Update information about Flamenco Server"""
    bl_idname = "flamenco.update"
    bl_label = "Update Flamenco info"

    def execute(self, context):
        user_preferences = context.user_preferences
        addon_prefs = user_preferences.addons[__name__].preferences
        serverurl = addon_prefs.flamenco_server
        wm = bpy.context.window_manager

        try:
            projects = requests.get('{0}/projects'.format(serverurl), timeout=1)
            settings_server = requests.get('{0}/settings'.format(serverurl), timeout=1)
            settings_managers = requests.get(
                '{0}/settings/managers'.format(serverurl), timeout=1)
            managers = requests.get('{0}/managers'.format(serverurl), timeout=1)
        except ConnectionError:
            self.report( {'ERROR'}, "Can't connect to server on {0}".format(serverurl) )
            return {'CANCELLED'}
        except Timeout:
            self.report( {'ERROR'}, "Timeout connecting to server on {0}".format(serverurl) )
            return {'CANCELLED'}

        wm.flamenco_projectCache = projects.text


        settings_server = settings_server.json()
        wm.flamenco_settingsServerIndex = 0
        wm.flamenco_settingsServer.clear()
        for setting in settings_server['settings']:
            sett_item = wm.flamenco_settingsServer.add()
            sett_item.name = str(setting['name'])
            sett_item.value = str(setting['value'])

        settings_managers = settings_managers.json()
        wm.flamenco_settingsManagerIndex = 0
        wm.flamenco_settingsManagers.clear()
        for manager in settings_managers:
            for setting in settings_managers[manager]:
                if setting == 'manager_name':
                    continue
                sett_item = wm.flamenco_settingsManagers.add()
                sett_item.manager = str(manager)
                sett_item.name = str(setting)
                sett_item.value = str(settings_managers[manager][setting])
                sett_item.new = False
                sett_item.manager_name = str(
                    settings_managers[manager]['manager_name'])

        managers = managers.json()
        wm.flamenco_managersIndex = 0
        wm.flamenco_managers.clear()
        for manager in managers:
            man_item = wm.flamenco_managers.add()
            man_item.name = managers[manager].get('name')
            man_item.id = managers[manager].get('id')

        return {'FINISHED'}

class saveManagerSetting (bpy.types.Operator):
    """Save Manager Setting"""
    bl_idname = "flamenco.save_manager_setting"
    bl_label = "Save Preferences"

    def execute(self, context):
        user_preferences = context.user_preferences
        addon_prefs = user_preferences.addons[__name__].preferences
        serverurl = addon_prefs.flamenco_server
        wm = context.window_manager
        selected_setting = wm.flamenco_settingsManagers[
            wm.flamenco_settingsManagerIndex]

        if selected_setting.name=="":
            return {'FINISHED'}

        url = "{0}/settings/managers/{1}/{2}".format(
            serverurl, selected_setting.manager, selected_setting.name)

        data = {'value': selected_setting.value}
        r = requests.post(url, data=data, timeout=20)

        selected_setting.new = False

        return {'FINISHED'}


class addManagerSetting (bpy.types.Operator):
    """Add a Manager Setting"""
    bl_idname = "flamenco.add_manager_setting"
    bl_label = "Add Manager Setting"
    def execute(self,context):
        wm = context.window_manager
        settings_collection = wm.flamenco_settingsManagers

        selected_setting = settings_collection[wm.flamenco_settingsManagerIndex]
        manager = wm.flamenco_managers[wm.flamenco_managersIndex]

        setting = settings_collection.add()
        setting.manager = str(manager.id)
        setting.manager_name = manager.name
        setting.name = ""
        setting.valur = ""
        wm.flamenco_settingsManagerIndex = len(settings_collection)-1
        return {'FINISHED'}


class bamToRenderfarm (bpy.types.Operator):
    """Save current file and send it to the Renderfarm using BAM pack"""
    bl_idname = "flamenco.send_job"
    bl_label = "Save and send"

    def execute(self, context):
        C = context
        D = bpy.data
        scn = C.scene
        wm = bpy.context.window_manager
        user_preferences = context.user_preferences
        addon_prefs = user_preferences.addons[__name__].preferences
        serverurl = addon_prefs.flamenco_server

        if not D.filepath:
            self.report({'ERROR'}, "Save your blend file first")
            return {'CANCELLED'}

        if wm.flamenco_jobName == "":
            self.report({'ERROR'}, "Name your Job")
            return {'CANCELLED'}


        # filepath = D.filepath

        # args = None

        job_settings = {
            'frame_start': scn.frame_start,
            'frame_end': scn.frame_end,
            'chunk_size': wm.flamenco_chunkSize,
            'filepath': os.path.split(D.filepath)[1],
            'render_settings': "",
            'format': "PNG",
            'command_name': wm.flamenco_command,
            }

        job_properties = {
            'project_id': int(wm.flamenco_project),
            'settings': json.dumps(job_settings),
            'name': wm.flamenco_jobName,
            'type': wm.flamenco_jobType,
            'managers': wm.flamenco_managers[wm.flamenco_managersIndex].id,
            'priority': wm.flamenco_priority,
            'start_job': wm.flamenco_startJob,
        }

        bpy.ops.wm.save_mainfile()

        tmppath = C.user_preferences.filepaths.temporary_directory
        zipname = "job"
        zippath = os.path.join(tmppath, "%s.zip" % zipname)

        try:
            subprocess.call(["bam", "pack", D.filepath, '-o', zippath])
        except:
            self.report({'ERROR'}, "Error running BAM, is it installed?")
            return {'CANCELLED'}

        render_file = [('jobfile',
                        ('jobfile.zip', open(zippath, 'rb'),
                        'application/zip'))]

        postserverurl = "{0}/jobs".format(serverurl)

        try:
            requests.post(
                postserverurl, files=render_file, data=job_properties)
        except ConnectionError:
            print ("Connection Error: {0}".format(postserverurl))

        return {'FINISHED'}


class MovPanelControl(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label = "Send Job"
    bl_category = "Flamenco"

    def draw(self, context):
        D = bpy.data
        wm = bpy.context.window_manager

        layout = self.layout
        col = layout.column()
        col.operator("flamenco.update")

        if len(project_list(self, context))==0:
            return
        if len(wm.flamenco_managers)==0:
            return

        if wm.flamenco_jobName == "" and D.filepath != "":
            wm.flamenco_jobName = os.path.split(D.filepath)[1]

        col.prop(wm, 'flamenco_project')
        col.prop(wm, 'flamenco_jobName')
        col.prop(wm, 'flamenco_jobType')
        col.prop(wm, 'flamenco_command')
        col.template_list(
            "UI_UL_list",
            "ui_lib_list_prop",
            wm,
            "flamenco_managers",
            wm,
            "flamenco_managersIndex",
            rows=5)
        col.prop(wm, 'flamenco_chunkSize')
        col.prop(wm, 'flamenco_priority')
        col.prop(wm, 'flamenco_startJob')
        col.operator("flamenco.send_job")

        """col.label(text="Server Settings")
        col.template_list(
            "UI_UL_list",
            "ui_lib_list_propp",
            wm,
            "flamenco_settingsServer",
            wm,
            "flamenco_settingsServerIndex",
            rows=5,
        )
        if len(wm.flamenco_settingsServer) > 0:
            setting = wm.flamenco_settingsServer[
                wm.flamenco_settingsServerIndex]
            col.prop(setting, "value")

        col.label(text="Manager Settings")
        col.template_list(
            "UI_UL_list",
            "ui_lib_list_proppp",
            wm,
            "flamenco_settingsManagers",
            wm,
            "flamenco_settingsManagerIndex",
            rows=5,
        )

        col.operator("flamenco.add_manager_setting")

        if len(wm.flamenco_settingsManagers) > 0:
            setting = wm.flamenco_settingsManagers[
                wm.flamenco_settingsManagerIndex]
            col.label(text=setting.manager_name)
            if setting.new:
                col.prop(setting, "name")
            col.prop(setting, "value")
            col.operator("flamenco.save_manager_setting")"""


jobType_list = [
    ('simple_blender_render', 'Simple', '', 1),
    ('tiled_blender_render', 'Tiled', '', 2),
    ]

manager_list = [
    ('1', 'Manager Dell', '', 1),
    ]

command_names = [
    ('default', 'Default', '', 1),
    ('multiview', 'Multiview', '', 2),
    ]

class flamencoManagers(bpy.types.PropertyGroup):
    name = StringProperty(
        name="Name",
        default="",
        options={'HIDDEN', 'SKIP_SAVE'})
    id = IntProperty(
        name="ID",
        default=0,
        options={'HIDDEN', 'SKIP_SAVE'})

class flamencoSettingsServer(bpy.types.PropertyGroup):
    name = StringProperty(
        name="Name",
        default="",
        options={'SKIP_SAVE'})
    value = StringProperty(
        name="Value",
        default="",
        options={'SKIP_SAVE'})

class flamencoSettingsManagers(bpy.types.PropertyGroup):
    manager = StringProperty(
        name="Manager",
        default="",
        options={'HIDDEN', 'SKIP_SAVE'})
    manager_name = StringProperty(
        name="Manager Name",
        default="",
        options={'HIDDEN', 'SKIP_SAVE'})
    name = StringProperty(
        name="Name",
        default="",
        options={'HIDDEN', 'SKIP_SAVE'})
    value = StringProperty(
        name="Value",
        default="",
        options={'HIDDEN', 'SKIP_SAVE'})
    new = BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})

def project_list(self, context):
    wm = context.window_manager

    try:
        project_cache = json.loads(wm.flamenco_projectCache)
    except:
        return []

    project_list = []
    for project in project_cache:
        project_list.append((project, project_cache[project].get('name'), ''))

    return project_list


def register():
    bpy.utils.register_module(__name__)
    wm = bpy.types.WindowManager

    wm.flamenco_project = EnumProperty(
        items=project_list, name="Projects", description="Flamenco Projects")
    wm.flamenco_projectCache = StringProperty(
        name="Project list cache", default="", options={'HIDDEN', 'SKIP_SAVE'})
    wm.flamenco_jobName = StringProperty(
        name="Job Name", default="", options={'HIDDEN', 'SKIP_SAVE'})
    wm.flamenco_jobType = EnumProperty(
        items=jobType_list, name="Job type", description="Flamenco Projects")
    wm.flamenco_chunkSize = IntProperty(
        name="Chunk Size",
        default=5,
        #hard_min=1,
        #hard_max=20,
        soft_min=1,
        #soft_max=20,
        options={'HIDDEN', 'SKIP_SAVE'})
    wm.flamenco_managers = CollectionProperty(
        type=flamencoManagers, name="Managers", description="Flamenco Managers")
    wm.flamenco_managersIndex = IntProperty(
        name="Manager Index", description="Currently selected Flamenco Manager")
    wm.flamenco_command = EnumProperty(
        items=command_names, name="Command", description="Flamenco Command")
    wm.flamenco_priority = IntProperty(
        name="Priority",
        default=50,
        soft_min=0,
        options={'HIDDEN', 'SKIP_SAVE'})
    wm.flamenco_startJob = BoolProperty(
        name="Start Job",
        options={'HIDDEN', 'SKIP_SAVE'})
    wm.flamenco_settingsServer = CollectionProperty(
        type=flamencoSettingsServer,
        name="Server Settings",
        description="Server Settings")
    wm.flamenco_settingsServerIndex = IntProperty(
        name="Server Setting Index",
        description="Currently selected Flamenco Server Setting")
    wm.flamenco_settingsManagers = CollectionProperty(
        type=flamencoSettingsManagers,
        name="Managers Settings",
        description="Managers Settings")
    wm.flamenco_settingsManagerIndex = IntProperty(
        name="Manager Setting Index",
        description="Currently selected Flamenco Manager Setting")


def unregister():
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()
