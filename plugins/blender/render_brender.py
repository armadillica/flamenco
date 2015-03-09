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
# from bpy.props import BoolProperty
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
            settings = requests.get('{0}/settings/render'.format(serverurl), timeout=1)
            managers = requests.get('{0}/managers'.format(serverurl), timeout=1)
        except ConnectionError:
            self.report( {'ERROR'}, "Can't connect to server on {0}".format(serverurl) )
            return {'CANCELLED'}
        except Timeout:
            self.report( {'ERROR'}, "Timeout connecting to server on {0}".format(serverurl) )
            return {'CANCELLED'}


        wm.flamenco_projectCache = projects.text


        managers = managers.json()

        # print ("Projects")
        # print (projects.json())
        # print ("Settings")
        # print (settings.json())
        # print ("Managers")
        # print (managers)

        wm.flamenco_managersIndex = 0
        wm.flamenco_managers.clear()
        for manager in managers:
            man_item = wm.flamenco_managers.add()
            man_item.name = managers[manager].get('name')
            man_item.id = managers[manager].get('id')

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
            'chunk_size': 5,
            'filepath': os.path.split(D.filepath)[1],
            'render_settings': "",
            'format': "PNG",
            }

        job_properties = {
            'project_id': int(wm.flamenco_project),
            'settings': json.dumps(job_settings),
            'name': wm.flamenco_jobName,
            'type': wm.flamenco_jobType,
            'managers': wm.flamenco_managers[wm.flamenco_managersIndex].id,
            'priority': wm.flamenco_priority
        }

        print (job_properties)
        
        amaranth_addon = False
        try:
            scn.use_unsimplify_render
            amaranth_addon = True
        except:
            pass

        tmp_simplify = scn.render.use_simplify
        if amaranth_addon and scn.use_unsimplify_render:
            scn.render.use_simplify = False

        bpy.ops.wm.save_mainfile()
        scn.render.use_simplify = tmp_simplify
        
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

        """project_folder = '/render/brender/gooseberry'

        if not D.filepath:
            self.report( {'ERROR'}, "Save your Blendfile first")
            return {'CANCELLED'}

        blendpath = os.path.split(D.filepath)[0]

        zipname = "{0}_{1}".format(
            strftime("%Y-%m-%d_%H-%M-%S"), os.path.split(D.filepath)[1][:-6])

        zippath = os.path.join(blendpath, "%s.zip" % zipname)
        renderfarmpath = os.path.join(project_folder, zipname)

        try:
            subprocess.call([ "bam", "pack", D.filepath, '-o', zippath ])
        except:
            self.report( {'ERROR'}, "Error running BAM, is it installed?")
            return {'CANCELLED'}

        try:
            subprocess.call([ "unzip", zippath, '-d', renderfarmpath ])
        except:
            self.report( {'ERROR'}, "Error running unzip or deleting zip")
            return {'CANCELLED'}"""

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

        #print(wm.flamenco_project)
        #print(wm.flamenco_managers)

        if len(project_list(self, context))==0:
            return
        if len(wm.flamenco_managers)==0:
            return

        if wm.flamenco_jobName == "" and D.filepath != "":
            wm.flamenco_jobName = os.path.split(D.filepath)[1]

        col.prop(wm, 'flamenco_project')
        col.prop(wm, 'flamenco_jobName')
        col.prop(wm, 'flamenco_jobType')
        # col.prop(wm, 'flamenco_managers')
        col.template_list(
            "UI_UL_list",
            "ui_lib_list_prop",
            wm,
            "flamenco_managers",
            wm,
            "flamenco_managersIndex",
            rows=5)
        col.prop(wm, 'flamenco_priority')
        col.operator("flamenco.send_job")


jobType_list = [
    ('simple_blender_render', 'Simple', '', 1),
    ('tiled_blender_render', 'Tiled', '', 2),
    ]

manager_list = [
    ('1', 'Manager Dell', '', 1),
    ]


class flamencoManagers(bpy.types.PropertyGroup):
    name = StringProperty(
        name="Name", default="", options={'HIDDEN', 'SKIP_SAVE'})
    id = IntProperty(
        name="ID", default=0, options={'HIDDEN', 'SKIP_SAVE'})


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
    wm.flamenco_managers = CollectionProperty(
        type=flamencoManagers, name="Managers", description="Flamenco Managers")
    wm.flamenco_managersIndex = IntProperty(
        name="Manager Index", description="Currently selected Flamenco Manager")
    wm.flamenco_priority = IntProperty(
        options={'HIDDEN', 'SKIP_SAVE'})


def unregister():
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()
