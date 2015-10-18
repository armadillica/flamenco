import os
import json
import logging

class job_compiler():
    @staticmethod
    def compile(job, project, create_task):
        parser = 'blender_render'
        job_settings = json.loads(job.settings)
        task_settings = dict(
            filepath=job_settings['filepath'],
            render_settings=job_settings['render_settings'],
            format=job_settings['format'],
            command_name=job_settings['command_name'],
            priority=job.priority,
            frame_start=job_settings['frames'].split('-')[0],
            frame_end=job_settings['frames'].split('-')[0]
        )

        tiles = 4
        task_settings['tiles'] = tiles

        task_type = 'tiled_blender_render_simple_mix'
        mix_task_id = create_task(job.id, task_type , task_settings, 'Mixing', None, parser)

        task_type = 'tiled_blender_render'
        for tile in range(0, tiles):
            task_settings['tile'] = tile
            name = 'Tile {0}'.format(tile)
            create_task(job.id, task_type, task_settings, name, mix_task_id, parser)


