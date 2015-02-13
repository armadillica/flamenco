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
      elif 'Linux' in worker.system:
         setting_blender_path = app.config['BLENDER_PATH_LINUX']
         setting_render_settings = app.config['SETTINGS_PATH_LINUX']
         file_path = settings['file_path_linux']
         output_path = settings['output_path_linux']

      if setting_blender_path is None:
         logging.info('[Debug] blender path is not set')
         return None

      blender_path = setting_blender_path

      if setting_render_settings is None:
         logging.warning("Render settings path not set!")
         return None

      tile_output_path= os.path.join( output_path, "tiled_{0}_".format(settings['tile']) )

      setting_render_settings = app.config['SETTINGS_PATH_LINUX']
      render_settings = os.path.join(
         setting_render_settings,
          settings['render_settings'])

      script_path=os.path.join(output_path , 'tile_mix')

      dir = os.path.dirname(__file__)
      template_path = os.path.join(dir, 'tiled_blender_render.template')
      with open (template_path, "r") as f:
         script=f.read()
      f.close()

      data="""
tile={0}
tiles={1}
      """.format(settings['tile'], settings['tiles'])

      script = script.replace("##VARS_INSERTED_HERE##",data)

      script_path=os.path.join(output_path , 'tile_{0}'.format(settings['tile']))

      try:
         os.mkdir(output_path)
      except:
         pass

      f = open(script_path,"w")
      f.write(script)
      f.close()

      task_command = [
      str( blender_path ),
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
      '--render-anim',
      '--enable-autoexec'
      ]

      return task_command
