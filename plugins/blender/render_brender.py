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


class brenderUpdate (bpy.types.Operator):
    """Update information about Flamenco Server"""
    bl_idname = "brender.update"
    bl_label = "Update Brender info"

    def execute(self, context):
        serverurl = "http://192.168.3.106:9999"
        wm = bpy.context.window_manager

        try:
            projects = requests.get('{0}/projects'.format(serverurl))
            settings = requests.get('{0}/settings/render'.format(serverurl))
            managers = requests.get('{0}/managers'.format(serverurl))
        except ConnectionError:
            print ("Connection Error: {0}".format(serverurl))


        wm.brender_projectCache = projects.text


        managers = managers.json()

        # print ("Projects")
        # print (projects.json())
        # print ("Settings")
        # print (settings.json())
        # print ("Managers")
        # print (managers)

        wm.brender_managersIndex = 0
        wm.brender_managers.clear()
        for manager in managers:
            man_item = wm.brender_managers.add()
            man_item.name = managers[manager].get('name')
            man_item.id = managers[manager].get('id')

        return {'FINISHED'}


class bamToRenderfarm (bpy.types.Operator):
    """Save current file and send it to the Renderfarm using BAM pack"""
    bl_idname = "brender.send_job"
    bl_label = "Save and send"

    def execute(self, context):
        C = context
        D = bpy.data
        scn = C.scene
        wm = bpy.context.window_manager

        if not D.filepath:
            self.report({'ERROR'}, "Save your Blendfile first")
            return {'CANCELLED'}

        if wm.brender_jobName == "":
            self.report({'ERROR'}, "Name your Job")
            return {'CANCELLED'}

        serverurl = "http://192.168.3.106:9999/jobs"

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
            'project_id': wm.brender_project,
            'settings': json.dumps(job_settings),
            'name': wm.brender_jobName,
            'type': wm.brender_jobType,
            'managers': wm.brender_managers[wm.brender_managersIndex].id,
            'priority': wm.brender_priority
        }

        print (job_properties)

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
        try:
            requests.post(
                serverurl, files=render_file, data=job_properties)
        except ConnectionError:
            print ("Connection Error: {0}".format(serverurl))

        """project_folder = '/render/brender/gooseberry'

        if not D.filepath:
            self.report( {'ERROR'}, "Save your Blendfile first")
            return {'CANCELLED'}

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

        if wm.brender_jobName == "" and D.filepath != "":
            wm.brender_jobName = os.path.split(D.filepath)[1]

        col = layout.column()
        col.prop(wm, 'brender_project')
        col.prop(wm, 'brender_jobName')
        col.prop(wm, 'brender_jobType')
        # col.prop(wm, 'brender_managers')
        col.template_list(
            "UI_UL_list",
            "ui_lib_list_prop",
            wm,
            "brender_managers",
            wm,
            "brender_managersIndex",
            rows=5)
        col.prop(wm, 'brender_priority')
        col.operator("brender.send_job")
        col.operator("brender.update")


jobType_list = [
    ('simple_blender_render', 'Simple', '', 1),
    ('tiled_blender_render', 'Tiled', '', 2),
    ]

manager_list = [
    ('1', 'Manager Dell', '', 1),
    ]


class brenderManagers(bpy.types.PropertyGroup):
    name = StringProperty(
        name="Name", default="", options={'HIDDEN', 'SKIP_SAVE'})
    id = IntProperty(
        name="ID", default=0, options={'HIDDEN', 'SKIP_SAVE'})


def project_list(self, context):
    wm = context.window_manager

    try:
        project_cache = json.loads(wm.brender_projectCache)
    except:
        return []

    project_list = []
    for project in project_cache:
        project_list.append((project, project_cache[project].get('name'), ''))

    return project_list


def register():
    bpy.utils.register_module(__name__)
    wm = bpy.types.WindowManager

    wm.brender_project = EnumProperty(
        items=project_list, name="Projects", description="Brender Projects")
    wm.brender_projectCache = StringProperty(
        name="Project list cache", default="", options={'HIDDEN', 'SKIP_SAVE'})
    wm.brender_jobName = StringProperty(
        name="Job Name", default="", options={'HIDDEN', 'SKIP_SAVE'})
    wm.brender_jobType = EnumProperty(
        items=jobType_list, name="Job type", description="Brender Projects")
    wm.brender_managers = CollectionProperty(
        type=brenderManagers, name="Managers", description="Brender Managers")
    wm.brender_managersIndex = IntProperty(
        name="Manager Index", description="Currently selected Brender Manager")
    wm.brender_priority = IntProperty(
        options={'HIDDEN', 'SKIP_SAVE'})


def unregister():
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()
