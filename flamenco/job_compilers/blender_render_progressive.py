from pathlib import PurePath
import typing

from bson import ObjectId

from pillar import attrs_extra

from . import blender_render, commands, register_compiler


@register_compiler('blender-render-progressive')
class BlenderRenderProgressive(blender_render.AbstractBlenderJobCompiler):
    """Progressive Blender render job.

    Creates a render task for each Cycles sample chunk, and creates merge
    tasks to merge those render outputs into progressively refining output.

    Intermediary files are created in a subdirectory of the render output path.
    """

    _log = attrs_extra.log('%s.BlenderRenderProgressive' % __name__)

    REQUIRED_SETTINGS = ('blender_cmd', 'filepath', 'render_output', 'frames', 'chunk_size',
                         'format', 'cycles_sample_count', 'cycles_num_chunks')

    def _compile(self, job):
        import math
        from .blender_render import intermediate_path

        self._log.info('Compiling job %s', job['_id'])
        self.validate_job_settings(job)
        self.job_settings = job['settings']

        # The render output contains a filename pattern, most likely '######' or
        # something similar. This has to be removed, so that we end up with
        # the directory that will contain the frames.
        self.render_output = PurePath(job['settings']['render_output'])
        self.render_path = self.render_output.parent
        self.intermediate_path = intermediate_path(job, self.render_path)

        destroy_interm_task_id = self._make_destroy_intermediate_task(job)
        rna_overrides_task_id = self._make_rna_overrides_task(job, destroy_interm_task_id)
        render_parent_task_id = rna_overrides_task_id or destroy_interm_task_id
        task_count = 1 + bool(rna_overrides_task_id)

        cycles_sample_count = int(self.job_settings['cycles_sample_count'])
        self.cycles_num_chunks = int(self.job_settings['cycles_num_chunks'])
        sample_count_per_chunk = int(math.ceil(float(cycles_sample_count) / self.cycles_num_chunks))

        next_merge_task_deps = []
        prev_samples_to = 0
        for cycles_chunk_idx in range(int(self.job_settings['cycles_num_chunks'])):
            # Compute the Cycles sample range for this chunk (chunk_idx in base-0), in base-1.
            cycles_samples_from = cycles_chunk_idx * sample_count_per_chunk + 1
            cycles_samples_to = min((cycles_chunk_idx + 1) * sample_count_per_chunk,
                                    cycles_sample_count)

            # Create render tasks for each frame chunk. Only this function uses the base-0
            # chunk/sample numbers, so we also convert to the base-1 numbers that Blender
            # uses.
            render_task_ids = self._make_progressive_render_tasks(
                job,
                'render-smpl%i-%i-frm%%s' % (cycles_samples_from, cycles_samples_to),
                render_parent_task_id,
                cycles_chunk_idx + 1,
                cycles_samples_from,
                cycles_samples_to,
                task_priority=-cycles_chunk_idx * 10,
            )
            task_count += len(render_task_ids)

            # Create progressive image merge tasks, based on previous list of render tasks
            # and the just-created list.
            if cycles_chunk_idx == 0:
                # Nothing to merge yet, just copy the first renders.
                publish_task_id = self._make_publish_first_chunk_task(
                    job,
                    render_task_ids,
                    cycles_samples_from,
                    cycles_samples_to,
                )
                task_count += 1
                next_merge_task_deps = len(render_task_ids) * [publish_task_id]
            else:
                # Both merge and render tasks should have same number of frame chunks.
                assert len(next_merge_task_deps) == len(render_task_ids)
                merge_task_ids = self._make_merge_tasks(
                    job,
                    'merge-to-smpl%i-frm%%s' % cycles_samples_to,
                    cycles_chunk_idx + 1,
                    next_merge_task_deps,
                    render_task_ids,
                    cycles_samples_to1=prev_samples_to,
                    cycles_samples_from2=cycles_samples_from,
                    cycles_samples_to2=cycles_samples_to,
                    task_priority=-cycles_chunk_idx * 10 - 1,
                )
                task_count += len(merge_task_ids)
                next_merge_task_deps = merge_task_ids
            prev_samples_to = cycles_samples_to

        self._log.info('Created %i tasks for job %s', task_count, job['_id'])

    def validate_job_settings(self, job):
        """Ensure that the job uses format=EXR."""
        super().validate_job_settings(job)

        from flamenco import exceptions

        render_format = job['settings']['format']
        if render_format.upper() != 'EXR':
            raise exceptions.JobSettingError(
                'Job %s must use format="EXR", not %r' % (job.get('_id', '-no-id-'), render_format))

        # This is quite a limitation, but makes our code to predict the
        # filename that Blender will use a lot simpler.
        render_output = job['settings']['render_output']
        if not render_output.endswith('######') or render_output.endswith('#######'):
            raise exceptions.JobSettingError(
                'Setting "render_output" must end in exactly 6 "#" marks.')

    def _make_destroy_intermediate_task(self, job: dict) -> ObjectId:
        """Removes the entire intermediate directory."""

        cmd = commands.RemoveTree(path=str(self.intermediate_path))
        task_id = self._create_task(job, [cmd], 'destroy-preexisting-intermediate',
                                    'file-management')
        return task_id

    def _make_publish_first_chunk_task(self, job: dict, parents: typing.List[ObjectId],
                                       cycles_samples_from: int,
                                       cycles_samples_to: int) -> ObjectId:
        """Publishes the first cycles-chunk of renders."""

        cmds: typing.List[commands.AbstractCommand] = [commands.MoveOutOfWay(
            src=str(self.render_path))]

        src_path = self._render_output(cycles_samples_from, cycles_samples_to)
        src_fmt = str(src_path).replace('######', '%06i.exr')
        dest_fmt = str(self.render_output).replace('######', '%06i.exr')

        for chunk_frames in self._iter_frame_chunks():
            for frame in chunk_frames:
                cmds.append(commands.CopyFile(
                    src=src_fmt % frame,
                    dest=dest_fmt % frame,
                ))

        task_id = self._create_task(job, cmds, 'publish-first-chunk', 'file-management',
                                    parents=parents)
        return task_id

    def _make_progressive_render_tasks(self,
                                       job, name_fmt, parents,
                                       cycles_chunk_idx,
                                       cycles_samples_from, cycles_samples_to,
                                       task_priority):
        """Creates the render tasks for this job.

        :param parents: either a list of parents, one for each task, or a
            single parent used for all tasks.
        :param cycles_chunk_idx: base-1 sample chunk index

        :returns: created task IDs, one render task per frame chunk.
        :rtype: list
        """

        from bson import ObjectId
        from flamenco.utils import iter_frame_range, frame_range_merge

        job_settings = job['settings']

        task_ids = []
        frame_chunk_iter = iter_frame_range(job_settings['frames'], job_settings['chunk_size'])
        for chunk_idx, chunk_frames in enumerate(frame_chunk_iter):
            frame_range = frame_range_merge(chunk_frames)
            frame_range_bstyle = frame_range_merge(chunk_frames, blender_style=True)

            name = name_fmt % frame_range

            render_output = self._render_output(cycles_samples_from, cycles_samples_to)

            task_cmds = [
                commands.BlenderRenderProgressive(
                    blender_cmd=job_settings['blender_cmd'],
                    filepath=job_settings['filepath'],
                    format=job_settings.get('format'),
                    # Don't render to actual render output, but to an intermediate file.
                    render_output=str(render_output),
                    frames=frame_range_bstyle,
                    cycles_num_chunks=self.cycles_num_chunks,
                    cycles_chunk=cycles_chunk_idx,
                    cycles_samples_from=cycles_samples_from,
                    cycles_samples_to=cycles_samples_to,
                )
            ]

            if isinstance(parents, list):
                parent_task_id = parents[chunk_idx]
            else:
                parent_task_id = parents

            if not isinstance(parent_task_id, ObjectId):
                raise TypeError('parents should be list of ObjectIds or ObjectId, not %s' % parents)

            task_id = self._create_task(
                job, task_cmds, name, 'blender-render',
                parents=[parent_task_id],
                priority=task_priority)
            task_ids.append(task_id)

        return task_ids

    def _render_output(self, cycles_samples_from, cycles_samples_to) -> PurePath:
        """Intermediate render output path, with ###### placeholder for the frame nr"""
        render_fname = 'render-smpl-%04i-%04i-frm-######' % (cycles_samples_from, cycles_samples_to)
        render_output = self.intermediate_path / render_fname
        return render_output

    def _merge_output(self, cycles_samples_to) -> PurePath:
        """Intermediate merge output path, with ###### placeholder for the frame nr"""
        merge_fname = 'merge-smpl-%04i-frm-######' % cycles_samples_to
        merge_output = self.intermediate_path / merge_fname
        return merge_output

    def _iter_frame_chunks(self) -> typing.Iterable[typing.List[int]]:
        """Iterates over the frame chunks"""
        from flamenco.utils import iter_frame_range

        yield from iter_frame_range(self.job_settings['frames'], self.job_settings['chunk_size'])

    def _make_merge_tasks(self, job, name_fmt,
                          cycles_chunk_idx,
                          parents1, parents2,
                          cycles_samples_to1,
                          cycles_samples_from2,
                          cycles_samples_to2,
                          task_priority):
        """Creates merge tasks for each chunk, consisting of merges for each frame.

        :param cycles_chunk_idx: base-1 sample chunk index

        """

        # Merging cannot happen unless we have at least two chunks
        assert cycles_chunk_idx >= 2

        from flamenco.utils import frame_range_merge

        task_ids = []

        weight1 = cycles_samples_to1
        weight2 = cycles_samples_to2 - cycles_samples_from2 + 1

        # Replace Blender formatting with Python formatting in render output path
        if cycles_chunk_idx == 2:
            # The first merge takes a render output as input1, subsequent ones take merge outputs.
            # Merging only happens from Cycles chunk 2 (it needs two inputs, hence 2 chunks).
            input1 = self._render_output(1, cycles_samples_to1)
        else:
            input1 = self._merge_output(cycles_samples_to1)
        input2 = self._render_output(cycles_samples_from2, cycles_samples_to2)
        output = self._merge_output(cycles_samples_to2)

        # Construct format strings from the paths.
        input1_fmt = str(input1).replace('######', '%06i.exr')
        input2_fmt = str(input2).replace('######', '%06i.exr')
        output_fmt = str(output).replace('######', '%06i.exr')
        final_dest_fmt = str(self.render_output).replace('######', '%06i.exr')

        for chunk_idx, chunk_frames in enumerate(self._iter_frame_chunks()):
            # Create a merge command for every frame in the chunk.
            task_cmds = []
            for framenr in chunk_frames:
                intermediate = output_fmt % framenr
                task_cmds.append(
                    commands.MergeProgressiveRenders(
                        input1=input1_fmt % framenr,
                        input2=input2_fmt % framenr,
                        output=intermediate,
                        weight1=weight1,
                        weight2=weight2,
                    ))
                task_cmds.append(
                    commands.CopyFile(
                        src=intermediate,
                        dest=final_dest_fmt % framenr,
                    ))

            name = name_fmt % frame_range_merge(chunk_frames)

            parent1 = parents1[chunk_idx]
            parent2 = parents2[chunk_idx]

            task_id = self._create_task(
                job, task_cmds, name, 'exr-merge',
                parents=[parent1, parent2],
                priority=task_priority)
            task_ids.append(task_id)

        return task_ids
