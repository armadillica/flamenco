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

      blender_path = setting_blender_path

      if setting_render_settings is None:
         logging.warning("Render settings path not set!")

      #tile_output_path="{0}_{1}".format(output_path, settings['tile'])
      tile_output_path="{0}/".format(output_path)

      render_settings = os.path.join(
         setting_render_settings,
          settings['render_settings'])

      #render_folder=os.path.split(tile_output_path)[0]

      for tile in range(0, settings['tiles']):
         script_path=os.path.join(output_path , 'tile_mix')
         script="""
import bpy

D=bpy.data
C=bpy.context

if not C.scene.use_nodes:
   C.scene.use_nodes=True

compo_nodes= bpy.context.scene.node_tree.nodes
compo_links= bpy.context.scene.node_tree.links

bpy.context.scene.render.use_border = False
bpy.context.scene.render.use_compositing = True
bpy.context.scene.render.image_settings.color_mode = 'RGB'

removing=True
while removing:
    removing=False
    for node in compo_nodes:
        if node.type=='R_LAYERS':
            compo_nodes.remove(node)
            removing=True
            break

output_node=None
for node in compo_nodes:
    print (node.type)
    if node.type=='COMPOSITE':
        output_node=node
        break

tiles=%s
for tile in range(0, tiles):
    node_name="imput_tile_{0}".format(tile)
    node_image=compo_nodes.new(type='CompositorNodeImage')
    node_image.name=node_name
    node_image.location.y=290*tile
    
    imagepath='%s_{0}0001.png'.format(tile)
    node_image.image=D.images.load(filepath=imagepath)
    
    if tile>0:
        node_name="mix_tile_{0}_{1}".format(tile, tile+1)
        node=compo_nodes.new(type='CompositorNodeMixRGB')
        node.name=node_name
        node.blend_type = 'SCREEN'
        node.location.y=60 + (290*tile)
        node.location.x=200+(200*tile)
        
        compo_links.new(node_image.outputs[0], node.inputs[1])
        try:
            compo_links.new(last_mix.outputs[0], node.inputs[2])
        except:
            compo_links.new(last_image.outputs[0], node.inputs[2])
            pass
        
        last_mix=node
        
    last_image=node_image
    
compo_links.new(last_mix.outputs[0], output_node.inputs[0])

      """ % (settings['tiles'], os.path.join(output_path, 'tiled'))

      #script_path=os.path.join(tile_output_path , 'tile_{0}'.format(settings['tile']))

      try:
         os.mkdir(tile_output_path)
      except:
         pass

      f = open(script_path,"w")
      f.write(script)
      f.close()


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