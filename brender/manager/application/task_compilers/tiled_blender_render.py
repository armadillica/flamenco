import os
import json
import logging

from application import app

class task_compiler():
    @staticmethod
    def compile(worker, task):

      settings=json.loads(task['settings'])

      if 'Darwin' in worker.system:
         setting_blender_path = app.config['BLENDER_PATH_OSX']
         setting_render_settings = app.config['SETTINGS_PATH_OSX']
         file_path = settings['file_path_osx']
         output_path = settings['output_path_osx']
      elif 'Windows' in worker.system:
         setting_blender_path = app.config['BLENDER_PATH_WIN']
         setting_render_settings = app.config['SETTINGS_PATH_WIN']
         file_path = settings['file_path_win']
         output_path = settings['output_path_win']
      else:
         setting_blender_path = app.config['BLENDER_PATH_LINUX']
         setting_render_settings = app.config['SETTINGS_PATH_LINUX']
         file_path = settings['file_path_linux']
         output_path = settings['output_path_linux']

      if setting_blender_path is None:
         logging.info('[Debug] blender path is not set')

      blender_path = setting_blender_path

      if setting_render_settings is None:
         logging.warning("Render settings path not set!")

      tile_output_path= os.path.join( output_path, "tiled_{0}".format(settings['tile']) )

      setting_render_settings = app.config['SETTINGS_PATH_LINUX']
      render_settings = os.path.join(
         setting_render_settings,
          settings['render_settings'])

      script="""
import bpy

render_context = bpy.context.scene.render

tile = {0}
tiles = {1}

bpy.context.scene.render.use_border = True
bpy.context.scene.render.use_compositing = False
bpy.context.scene.render.image_settings.color_mode = 'RGB'

render_context.border_max_x = 1
render_context.border_min_x = 0

render_context.border_min_y = tile/tiles
render_context.border_max_y = ((tile+1)/tiles)
      """.format(settings['tile'], settings['tiles'])

      script_path=os.path.join(output_path , 'tile_{0}'.format(settings['tile']))

      try:
         os.mkdir(output_path)
      except:
         pass

      f = open(script_path,"w")
      f.write(script)
      f.close()

      #TODO the command will be in the database,
      #and not generated in the fly
      task_command = [
      str( app.config['BLENDER_PATH_LINUX'] ),
      '--background',
      str( file_path ),
      '--render-output',
      str(tile_output_path),
      '--python',
      str(script_path),
      '--frame-start' ,
      str(settings['frame_start']),
      '--frame-end',
      str(settings['frame_end']),
      '--render-format',
      str(settings['format']),
      '--render-anim',
      '--enable-autoexec'
      ]

      return task_command