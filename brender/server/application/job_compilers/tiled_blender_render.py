import os
import json
import logging

class job_compiler():
    @staticmethod
    def compile(job, project, create_task):
        parser='blender_render'
        
        job_settings = json.loads(job.settings)
        task_settings={}
        task_settings['filepath'] = job_settings['filepath']
        task_settings['render_settings'] = job_settings['render_settings']
        task_settings['format'] = job_settings['format']

        #project = Project.query.filter_by(id = job.project_id).first()
        filepath = task_settings['filepath']
        task_settings['file_path_linux'] = os.path.join(project.path_linux, filepath)
        task_settings['file_path_win'] = os.path.join(project.path_win, filepath)
        task_settings['file_path_osx'] = os.path.join(project.path_osx, filepath)
        #task_settings['settings'] = task.settings
        task_settings['output_path_linux'] = os.path.join(project.render_path_linux, str(job.id))
        task_settings['output_path_win'] = os.path.join(project.render_path_win, str(job.id))
        task_settings['output_path_osx'] = os.path.join(project.render_path_osx, str(job.id))
        task_settings['priority'] = job.priority

        task_settings['frame_start']=job_settings['frame_start']
        task_settings['frame_end']=job_settings['frame_start']

        tiles = 4
        task_settings['tiles']=tiles

        task_type='tiled_blender_render_simple_mix'
        mix_task_id=create_task(job.id, task_type , task_settings, 'Mixing', None, parser)

        task_type='tiled_blender_render'
        for tile in range(0, tiles):
            task_settings['tile']=tile
            name = 'Tile {0}'.format(tile)
            create_task(job.id, task_type, task_settings, name, mix_task_id, parser)

        