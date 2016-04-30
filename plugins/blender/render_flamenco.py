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
    "author": "Eibriel, Francesco Siddi",
    "version": (0, 5),
    "blender": (2, 73, 0),
    "location": "View3D > Tool Shelf > Flamenco",
    "description": "BAM pack current file and send it to the Flamenco Renderfarm",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Render"}

import bpy
import sys
import os
import json
import requests
import subprocess
import uuid
# from time import strftime

from bpy.props import IntProperty
from bpy.props import BoolProperty
from bpy.props import StringProperty
from bpy.props import EnumProperty
from bpy.props import CollectionProperty

from requests.exceptions import ConnectionError
from requests.exceptions import Timeout

from bpy.types import AddonPreferences

class ProfilesUtility():
    """Class that leverages the blender-id authentication system"""
    def __new__(cls, *args, **kwargs):
        raise TypeError("Base class may not be instantiated")

    @staticmethod
    def get_profiles_file():
        """Returns the profiles.json filepath from a .blender_id folder in the user
        home directory. If the file does not exist we create one with the basic data
        structure.
        """
        profiles_path = os.path.join(os.path.expanduser('~'), '.blender_id')
        profiles_file = os.path.join(profiles_path, 'profiles.json')
        if not os.path.exists(profiles_file):
            profiles = [{
                "username" : "",
                "token" : "",
                "is_active" : False}]
            try:
                os.makedirs(profiles_path)
            except FileExistsError:
                pass
            except Exception as e:
                raise e

            import json
            with open(profiles_file, 'w') as outfile:
                json.dump(profiles, outfile)
        return profiles_file

    @classmethod
    def credentials_load(cls):
        """Loads the credentials from a profile file. TODO: add a username
        arg so that one out of many identities can be retrieved.
        """
        import json
        profiles_file = cls.get_profiles_file()
        with open(profiles_file) as f:
            return json.load(f)

    @classmethod
    def get_active_profile(cls):
        """Pick the active profile from the profiles.json. If no active
        profile is found we return None.
        """
        profiles = ProfilesUtility.credentials_load()
        index = next((index for (index, d) in enumerate(profiles) if d["is_active"] == True), None)
        if index is not None:
            return profiles[index]
        else:
            return None

# TODO move into proper utils module
suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
def humansize(nbytes):
    if nbytes == 0: return '0 B'
    i = 0
    while nbytes >= 1024 and i < len(suffixes)-1:
        nbytes /= 1024.
        i += 1
    f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])

class flamencoPreferences(AddonPreferences):
    bl_idname = __name__

    flamenco_server = StringProperty(
        name="Flamenco Server URL",
        default="http://127.0.0.1:9999",
        options={'HIDDEN', 'SKIP_SAVE'})

    bam_binary = StringProperty(
        name="BAM binary",
        default="bam",
        options={'HIDDEN','SKIP_SAVE'})

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "flamenco_server")
        layout.prop(self, "bam_binary")

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
            timeout = 5
            projects = requests.get(
                '{0}/projects'.format(serverurl), timeout=timeout)
            settings_server = requests.get(
                '{0}/settings'.format(serverurl), timeout=timeout)
            settings_managers = requests.get(
                '{0}/settings/managers'.format(serverurl), timeout=timeout)
            managers = requests.get(
                '{0}/managers'.format(serverurl), timeout=timeout)
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
    bl_label = "Save and Send"

    def execute(self, context):
        C = context
        D = bpy.data
        scn = C.scene
        wm = bpy.context.window_manager
        user_preferences = context.user_preferences
        addon_prefs = user_preferences.addons[__name__].preferences
        serverurl = addon_prefs.flamenco_server


        job_name = wm.flamenco_jobName

        if not D.filepath:
            self.report({'ERROR'}, "Save your blend file first")
            return {'CANCELLED'}

        if job_name == "":
            self.report({'ERROR'}, "Name your Job")
            return {'CANCELLED'}

        # We retrieve the username via the .blender_id profiles file. If no file
        # is available we fail silently and set the username to "default"
        profile = ProfilesUtility.get_active_profile()
        if profile:
            username = profile['username']
        else:
            username = "default"

        job_settings = {
            'frames': "{0}-{1}".format(scn.frame_start, scn.frame_end),
            'chunk_size': wm.flamenco_chunkSize,
            'filepath': os.path.split(D.filepath)[1],
            'render_settings': "",
            'format': wm.flamenco_file_format,
            'command_name': wm.flamenco_command,
            }

        job_properties = {
            'project_id': int(wm.flamenco_project),
            'settings': json.dumps(job_settings),
            'name': job_name,
            'type': wm.flamenco_jobType,
            'managers': wm.flamenco_managers[wm.flamenco_managersIndex].id,
            'priority': wm.flamenco_priority,
            'username': username,
            #'start_job': wm.flamenco_startJob,
            # We always submit the job as not started, until we fix the server
            # behavior. See comments belo about startJob.
            'start_job': False
        }

        use_extension = C.scene.render.use_file_extension
        C.scene.render.use_file_extension = True
        bpy.ops.wm.save_mainfile()
        C.scene.render.use_file_extension = use_extension

        tmppath = C.user_preferences.filepaths.temporary_directory
        bam_binary=addon_prefs.bam_binary
        # Generate a UUID and attach it to the zipfile
        zipname = "jobfile_{0}".format(str(uuid.uuid1()))
        zippath = os.path.join(tmppath, "{0}.zip".format(zipname))

        try:
            print("Creating BAM archive at {0}".format(zippath))
            command = [bam_binary, "pack", D.filepath, '-o', zippath]

            # If we do not want to pack large files
            exclude_pattern = []
            if wm.flamenco_pack_alembic_caches is False:
                exclude_pattern.append('*.abc')
            if wm.flamenco_pack_exr_sequences is False:
                exclude_pattern.append('*.exr')
                exclude_pattern.append('*.jpg')
                exclude_pattern.append('*.png')
            if wm.flamenco_pack_movie_files is False:
                exclude_pattern.append('*.mov')
                exclude_pattern.append('*.avi')
            if wm.flamenco_pack_audio_files is False:
                exclude_pattern.append('*.wav')
                exclude_pattern.append('*.mp3')

            if exclude_pattern:
                pattern = ";".join(exclude_pattern)
                command.extend(["--exclude", pattern])
            subprocess.call(command)

            # We give feedback abouth the end of the packing
            statinfo = os.stat(zippath)
            print ("Created a {0} BAM archive".format(
                humansize(statinfo.st_size)))

        except:
            self.report({'ERROR'}, "Error running BAM. Is it installed?")
            return {'CANCELLED'}

        render_file = None
        if wm.flamenco_submit_archive:
            render_file = [('jobfile',
                            ('jobfile.zip', open(zippath, 'rb'),
                            'application/zip'))]

        server_job_url = "{0}/jobs".format(serverurl)

        try:
            r = requests.post(server_job_url, data=job_properties)
            r = r.json()
        except ConnectionError:
            print ("Connection Error: {0}".format(server_job_url))

        # If we are submitting the archived file (can be serveral GB large)
        if wm.flamenco_submit_archive:
            server_job_file_url = "{0}/jobs/file/{1}".format(
                serverurl,  r['id'])
            # Stream the data to the server
            with open(zippath, 'rb') as f:
                print ("Sending {0} file to server...".format(
                    humansize(statinfo.st_size)))
                p = requests.post(server_job_file_url, data=f)
            print ("Done")
            # Cleanup the temp file
            try:
                print("Removing BAM archive")
                os.remove(zippath)
            except OSError:
                print("Failed to removed BAM archive")

        return {'FINISHED'}

class MovPanelControl(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_label = "Send Job"
    bl_category = "Flamenco"

    def draw(self, context):
        D = bpy.data
        wm = bpy.context.window_manager
        scene = context.scene

        layout = self.layout
        col = layout.column()
        col.operator("flamenco.update", icon="FILE_REFRESH")

        col.separator()

        if len(project_list(self, context)) == 0:
            return
        if len(wm.flamenco_managers) == 0:
            return

        # Try to build a nice name for the job (this is done only once, then
        # the user has to update it himself). The name looks like this:
        # JOB_NAME | RENDER_RESOLUTION | SAMPLES

        if wm.flamenco_jobName == "" and D.filepath != "":
            file_name = os.path.split(D.filepath)[1]
            job_name = os.path.splitext(file_name)[0]
            render_size = scene.render.resolution_percentage
            if scene.render.engine == 'CYCLES':
                samples_count = "{0}S".format(scene.cycles.samples)
            else:
                samples_count = ""
            wm.flamenco_jobName = u"{0} | {1}% | {2}".format(
                job_name, render_size, samples_count)

        col.prop(wm, 'flamenco_project')
        col.prop(wm, 'flamenco_jobName')
        col.prop(wm, 'flamenco_jobType')
        col.prop(wm, 'flamenco_file_format')
        if wm.flamenco_jobType in ['blender_bake_anim_cache']:
            col.label(text="Objects to Bake:")
            for obj in context.selected_objects:
                if obj.cache_library:
                    col.label(text="- {0}".format(obj.name))
        col.prop(wm, 'flamenco_command')

        col.separator()

        col.template_list(
            "UI_UL_list",
            "ui_lib_list_prop",
            wm,
            "flamenco_managers",
            wm,
            "flamenco_managersIndex",
            rows=5)

        col.separator()

        # Set the job priority (betweeen 0 and 100)
        col.prop(wm, 'flamenco_priority')

        if not wm.flamenco_jobType in ['blender_bake_anim_cache']:
            col.prop(wm, 'flamenco_chunkSize')
        # Show info to help the user to determine a good chunk size
        row = col.row(align=True)

        count_frames = scene.frame_end - scene.frame_start + 1
        row.label("Frames Count: {0}".format(count_frames))
        count_chunks = int(count_frames / wm.flamenco_chunkSize)
        if count_chunks < 1: count_chunks = 1
        row.label("Chunks Count: {0}".format(count_chunks))

        # Automatically start the job. Currenlty commented, since we create a job
        # and could set it to started even before the actual file is uploaded
        # col.prop(wm, 'flamenco_startJob')

        col.separator()

        col.prop(wm, 'flamenco_submit_archive')
        col.prop(wm, 'flamenco_pack_alembic_caches')
        col.prop(wm, 'flamenco_pack_exr_sequences')
        col.prop(wm, 'flamenco_pack_movie_files')
        col.prop(wm, 'flamenco_pack_audio_files')

        col.separator()

        col.operator("flamenco.send_job", icon="APPEND_BLEND")

jobType_list = [
    ('blender_simple_render', 'Simple', '', 1),
    ('tiled_blender_render', 'Tiled', '', 2),
    ('blender_bake_anim_cache', 'Bake Anim Cache', '', 3),
    ('blender_opengl_render', 'OpenGL Render', '', 4),
    ]

command_names = [
    ('default', 'Default', '', 1),
    ('multiview', 'Multiview', '', 2),
    ('latest', 'Latest', '', 3),
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
    if project_cache:
        for project in project_cache:
            project_list.append((project, project_cache[project].get('name'), ''))

    return project_list

def register():
    bpy.utils.register_module(__name__)
    wm = bpy.types.WindowManager

    # Project
    wm.flamenco_project = EnumProperty(
        items=project_list, name="Projects", description="Flamenco Projects")
    wm.flamenco_projectCache = StringProperty(
        name="Project list cache", default="", options={'HIDDEN', 'SKIP_SAVE'})
    # Job Name
    wm.flamenco_jobName = StringProperty(
        name="Job Name", default="", options={'HIDDEN', 'SKIP_SAVE'})
    # Job Type
    wm.flamenco_jobType = EnumProperty(
        items=jobType_list, name="Job type", description="Type of job available")
    # File Format
    wm.flamenco_file_format = EnumProperty(
        items=[('EXR', 'EXR', ''), ('JPEG', 'JPEG', ''), ('PNG', 'PNG', ''),
            ('JPEG2000', 'JPEG2000', '') ],
        name="File Format",
        description="Output file format for the job")
    # Chunk Size
    wm.flamenco_chunkSize = IntProperty(
        name="Chunk Size",
        description="Number of chunks in which the render will be divided.",
        default=5,
        soft_min=1,
        options={'HIDDEN', 'SKIP_SAVE'})
    # Managers
    wm.flamenco_managers = CollectionProperty(
        type=flamencoManagers, name="Managers", description="Flamenco Managers")
    wm.flamenco_managersIndex = IntProperty(
        name="Manager Index", description="Currently selected Flamenco Manager")
    # Command (Blender Version)
    wm.flamenco_command = EnumProperty(
        items=command_names, name="Command", description="Flamenco Command")
    # Priority
    wm.flamenco_priority = IntProperty(
        name="Priority",
        description="A value between 0 and 100. The closer to 100, the higher the priority.",
        default=50,
        soft_min=0,
        soft_max=100,
        options={'HIDDEN', 'SKIP_SAVE'})
    # Start Job
    wm.flamenco_startJob = BoolProperty(
        name="Start Job",
        description="As soon the file is sent to the server, the job will be started.",
        options={'HIDDEN', 'SKIP_SAVE'})
    # Send Packed file
    wm.flamenco_submit_archive = BoolProperty(
        name="Send Packed File",
        description="If unchecked, the file will be BAM packed, but not sent to the server. \
This will have to be done by hand.",
        options={'HIDDEN', 'SKIP_SAVE'},
        default=True)
    # Pack Alembic Caches
    wm.flamenco_pack_alembic_caches = BoolProperty(
        name="Pack Alembic Caches",
        description="If checked, .abc caches will be added to the bam archive. \
This can generate very large files.",
        options={'HIDDEN', 'SKIP_SAVE'},
        default=False)
    # Pack EXR files
    wm.flamenco_pack_exr_sequences = BoolProperty(
        name="Pack EXR sequences",
        description="If checked, .exr image sequences will be included in the bam archive. \
This can generate very large files.",
        options={'HIDDEN', 'SKIP_SAVE'},
        default=False)
    # Pack movie files
    wm.flamenco_pack_movie_files = BoolProperty(
        name="Pack movie files",
        description="If checked, .mov and .avi files will be included in the bam archive. \
This can generate very large files.",
        options={'HIDDEN', 'SKIP_SAVE'},
        default=False)
    # Pack movie files
    wm.flamenco_pack_audio_files = BoolProperty(
        name="Pack audio files",
        description="If checked, .wav and .mp3 files will be included in the bam archive. \
    This can generate very large files.",
        options={'HIDDEN', 'SKIP_SAVE'},
        default=False)

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
