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
    "name": "Brender Integration",
    "author": "Eibriel",
    "version": (0,3),
    "blender": (2, 73, 0),
    "location": "View3D > Tool Shelf > Brender",
    "description": "BAM pack current file and send it to the Brender Renderfarm",
    "warning": "Warning!",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Render"}

import bpy
import os
import json
import requests
import subprocess
from time import strftime

from bpy.props import IntProperty
from bpy.props import BoolProperty
from bpy.props import StringProperty
from bpy.props import EnumProperty

from requests.exceptions import ConnectionError


class bamToRenderfarm (bpy.types.Operator):
    """Save current file and send it to the Renderfarm using BAM pack"""
    bl_idname = "brender.send_job"
    bl_label = "Save and send"

    def execute(self,context):
        C = context
        D = bpy.data
        scn = C.scene
        wm = bpy.context.window_manager

        if not D.filepath:
            self.report( {'ERROR'}, "Save your Blendfile first")
            return {'CANCELLED'}

        if wm.brender_JobName == "":
            self.report( {'ERROR'}, "Name your Job")
            return {'CANCELLED'}

        serverurl = "http://localhost:9999/jobs"

        filepath = D.filepath

        args = None

        job_settings = {
            'frame_start' : scn.frame_start,
            'frame_end' : scn.frame_end,
            'chunk_size' : 5,
            'filepath' : "",
            'render_settings' : "",
            'format' : "PNG",
            }

        job_properties = {
            'project_id':wm.brender_project,
            'settings':json.dumps(job_settings),
            'name':wm.brender_jobName,
            'status':"",
            'type':wm.brender_jobType,
            'managers':wm.brender_managers,
            'priority':wm.brender_priority
        }

        print (job_properties)

        render_file = [('jobfile', ('jobfile.zip', open(filepath, 'rb'), 'application/zip'))]
        try:
            r = requests.post(serverurl, files = render_file , data = job_properties)
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

        zipname = "{0}_{1}".format(strftime("%Y-%m-%d_%H-%M-%S"), os.path.split(D.filepath)[1][:-6])

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
    bl_label = "Renderfarm"
    bl_category = "Brender"

    def draw(self,context):
        wm = bpy.context.window_manager
        layout = self.layout

        col = layout.column()
        col.prop(wm, 'brender_project')
        col.prop(wm, 'brender_jobName')
        col.prop(wm, 'brender_jobType')
        col.prop(wm, 'brender_managers')
        col.prop(wm, 'brender_priority')
        col.operator("brender.send_job")


project_list = [
    ('1', 'TestProject', '', 1),
    ]

jobType_list = [
    ('simple_blender_render', 'Simple', '', 1),
    ('tiled_blender_render', 'Tiled', '', 2),
    ]

manager_list = [
    ('1', 'Manager Dell', '', 1),
    ]

def register():
    wm = bpy.types.WindowManager
    wm.brender_project = EnumProperty(items = project_list, name="Projects", description="Brender Projects")
    wm.brender_jobName = StringProperty(name="Job Name", default="", options={'HIDDEN', 'SKIP_SAVE'})
    wm.brender_jobType = EnumProperty(items = jobType_list, name="Job type", description="Brender Projects")
    wm.brender_managers = EnumProperty(items = manager_list, name="Managers", description="Brender Managers")
    wm.brender_priority = IntProperty(options={'HIDDEN', 'SKIP_SAVE'})
    bpy.utils.register_module(__name__)

def unregister():
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()

