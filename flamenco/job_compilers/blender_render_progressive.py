import math
from pathlib import PurePath
import typing

import attr
from bson import ObjectId

from pillar import attrs_extra

from . import blender_render, commands, register_compiler

SampleGenerator = typing.Callable[[int], float]


@attr.s(auto_attribs=True)
class ChunkGenerator:
    """Cycles sample chunk generator."""
    sample_count: int
    sample_cap: int

    uncapped_chunks: int = 5
    """For testing with less than 5 chunks.

    5 chunks, 400 samples, and a sample cap of 100 gives pleasant results for
    the Blender Animation Studio, which is why those values were chosen here.
    """

    def __iter__(self) -> typing.Iterator[typing.Tuple[int, int]]:
        """Return a new iterator of sample chunks."""
        sample_generator = self._subquadratic_samples()
        return self._sample_chunks(sample_generator)

    def _sample_chunks(self, generator: SampleGenerator) -> typing.Iterator[typing.Tuple[int, int]]:
        """Generator, yield (chunk_start, chunk_end) tuples.

        The `chunk_start` and `chunk_end` return values are base-1, as
        expected by the Cycles CLI args.

        :param generator: function that takes a chunk index (base-0) and
            returns the start sample index of that chunk.
        """
        last_sample = 0
        generation = 0
        sample_count = self.sample_count
        sample_cap = self.sample_cap

        while last_sample < sample_count:
            sample = int(round(generator(generation)))
            generation += 1

            this_chunk = sample - last_sample
            if this_chunk > sample_cap:
                break

            yield last_sample + 1, sample
            last_sample = sample

        if last_sample >= sample_count:
            return

        # Divide the remaining samples into chunks of no more than
        # 'sample_cap', in such a way that the number of samples per
        # chunk is as uniform as possible.
        samples_left = sample_count - last_sample
        nr_of_tasks = int(math.ceil(samples_left / sample_cap))
        new_cap = samples_left / nr_of_tasks
        # print('samples left:', samples_left)
        # print('nr of tasks:', nr_of_tasks)
        # print('new cap:', new_cap)
        while last_sample < sample_count:
            sample = min(last_sample + new_cap, sample_count)
            yield int(math.floor(last_sample)) + 1, int(math.floor(sample))
            last_sample = sample

    def _subquadratic_samples(self) -> SampleGenerator:
        # These values give pleasant results for the Blender Animation Studio.
        start_count = self.sample_count / 40
        e = 5 / 3
        uncapped_chunks = self.uncapped_chunks

        def _subquadratic(chunk_index: int) -> float:
            """Sub-quadratic sample chunk function.

            This divides the samples into an almost-quadratic curve and 5 chunks.
            Due to capping of the number of samples per chunks more than 5 are
            expected. However, after the 3rd chunk or so it's desirable to just
            hit the cap and have constant-sized chunks.
            """
            return ((self.sample_count - start_count) ** (1 / e) /
                    (uncapped_chunks - 1) * chunk_index) ** e + start_count

        return _subquadratic


@register_compiler('blender-render-progressive')
class BlenderRenderProgressive(blender_render.AbstractBlenderJobCompiler):
    """Progressive Blender render job.

    Creates a render task for each Cycles sample chunk, and creates merge
    tasks to merge those render outputs into progressively refining output.

    Intermediary files are created in a subdirectory of the render output path.

    To make things simple, we choose one chunk per sample. This requires
    Blender 7744203b7fde3 or newer (from Tue Jan 29 18:08:12 2019 +0100).

    NOTE: progressive rendering does not work with the denoiser.
    """

    _log = attrs_extra.log('%s.BlenderRenderProgressive' % __name__)

    REQUIRED_SETTINGS = ('blender_cmd', 'filepath', 'render_output', 'frames', 'chunk_size',
                         'format', 'cycles_sample_count', 'cycles_sample_cap', 'fps')

    # So that unit tests can override this value and produce smaller jobs.
    _uncapped_chunk_count = 5

    def _compile(self, job: dict):
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
        cycles_sample_cap = int(self.job_settings.get('cycles_sample_cap', 100))

        next_merge_task_deps = []
        next_preview_images_tid: typing.Optional[ObjectId] = None
        next_preview_video_tid: typing.Optional[ObjectId] = None
        prev_samples_to = 0

        self.chunk_generator = ChunkGenerator(cycles_sample_count, cycles_sample_cap,
                                              self._uncapped_chunk_count)

        for cycles_chunk_idx, (cycles_chunk_start, cycles_chunk_end) in \
                enumerate(self.chunk_generator):
            # Create render tasks for each frame chunk. Only this function uses the base-0
            # chunk/sample numbers, so we also convert to the base-1 numbers that Blender
            # uses.
            render_task_priority = -cycles_chunk_idx * 10
            render_task_ids = self._make_progressive_render_tasks(
                job,
                'render-smpl%i-%i-frm%%s' % (cycles_chunk_start, cycles_chunk_end),
                render_parent_task_id,
                cycles_sample_count,  # We use 1 chunk = 1 sample
                cycles_chunk_start,
                cycles_chunk_end,
                task_priority=render_task_priority,
            )
            task_count += len(render_task_ids)

            # Create progressive image merge tasks, based on previous list of render tasks
            # and the just-created list.
            if cycles_chunk_idx == 0:
                # Nothing to merge yet, just copy the first renders.
                publish_task_id = self._make_publish_task(
                    job,
                    render_task_ids,
                    cycles_chunk_start,
                    cycles_chunk_end,
                    task_priority=render_task_priority - 2,
                    is_first=True,
                )
                next_preview_images_tid, next_preview_video_tid = self._make_previews(
                    job, [publish_task_id], next_preview_images_tid, next_preview_video_tid,
                    task_priority=render_task_priority - 3)
                task_count += 3
                next_merge_task_deps = render_task_ids
            else:
                # Both merge and render tasks should have same number of frame chunks.
                assert len(next_merge_task_deps) == len(render_task_ids)
                merge_task_ids = self._make_merge_tasks(
                    job,
                    'merge-to-smpl%i-frm%%s' % cycles_chunk_end,
                    cycles_chunk_idx + 1,
                    next_merge_task_deps,
                    render_task_ids,
                    cycles_chunks_to1=prev_samples_to,
                    cycles_chunks_from2=cycles_chunk_start,
                    cycles_chunks_to2=cycles_chunk_end,
                    task_priority=render_task_priority - 1,
                )

                publish_task_id = self._make_publish_task(
                    job,
                    merge_task_ids,
                    1,
                    cycles_chunk_end,
                    task_priority=render_task_priority - 2,
                    is_first=False,
                )
                next_preview_images_tid, next_preview_video_tid = self._make_previews(
                    job, [publish_task_id], next_preview_images_tid, next_preview_video_tid,
                    task_priority=render_task_priority - 3)

                task_count += len(merge_task_ids) + 3
                next_merge_task_deps = merge_task_ids
            prev_samples_to = cycles_chunk_end

        self._log.info('Created %i tasks for job %s', task_count, job['_id'])

    def validate_job_settings(self, job):
        """Ensure that the job uses format=EXR."""
        from flamenco import exceptions

        job_id_str = job.get('_id', '')
        if job_id_str:
            job_id_str = f'{job_id_str} '
        if job['settings'].get('cycles_num_chunks'):
            # End of January 2019 we changed how progressive rendering works.
            # Users no longer provide the number of chunks, but the maximum
            # number of samples per render task.
            raise exceptions.JobSettingError(
                f'Job {job_id_str}was created using outdated Blender Cloud add-on, please upgrade.')

        super().validate_job_settings(job)

        render_format = job['settings']['format']
        if render_format.upper() != 'EXR':
            raise exceptions.JobSettingError(
                f'Job {job_id_str}must use format="EXR", not {render_format!r}')

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

    def _make_publish_task(self, job: dict, parents: typing.List[ObjectId],
                           cycles_samples_from: int,
                           cycles_samples_to: int,
                           task_priority: int,
                           *,
                           is_first: bool) -> ObjectId:
        """Publish the progressive result."""

        cmds: typing.List[commands.AbstractCommand] = []

        if is_first:
            cmds.append(commands.MoveOutOfWay(src=str(self.render_path)))
            src_path = self._render_output(cycles_samples_from, cycles_samples_to)
        else:
            src_path = self._merge_output(cycles_samples_to)

        src_fmt = str(src_path).replace('######', '%06i.exr')
        dest_fmt = str(self.render_output).replace('######', '%06i.exr')

        for chunk_frames in self._iter_frame_chunks():
            for frame in chunk_frames:
                cmds.append(commands.CopyFile(
                    src=src_fmt % frame,
                    dest=dest_fmt % frame,
                ))

        task_name = f'publish-samples-{cycles_samples_to}'
        task_id = self._create_task(job, cmds, task_name, 'file-management',
                                    parents=parents, priority=task_priority)
        return task_id

    def _make_previews(self, job: dict, parents: typing.List[ObjectId],
                       parent_images_tid: typing.Optional[ObjectId],
                       parent_video_tid: typing.Optional[ObjectId],
                       task_priority: int) -> typing.Tuple[ObjectId, ObjectId]:
        """Converts EXR files in the render output directory to JPEG files.

        This constructs two tasks, one of type 'blender-render' and one of
        type 'video-encoding'.

        :return: (images task ID, video task ID)
        """

        job_settings = job['settings']
        cmds = [
            commands.ExrSequenceToJpeg(
                blender_cmd=job_settings['blender_cmd'],
                filepath=job_settings['filepath'],
                exr_directory=str(self.render_path),
                output_pattern='preview-######',
            ),
        ]

        image_parents = parents[:]
        if parent_images_tid:
            image_parents.insert(0, parent_images_tid)
        images_task_id = self._create_task(job, cmds, 'create-preview-images', 'blender-render',
                                           parents=image_parents, priority=task_priority)

        cmds = [
            commands.CreateVideo(
                input_files=str(self.render_path / 'preview-*.jpg'),
                output_file=str(self.render_path / 'preview.mkv'),
                fps=job_settings['fps'],
            )
        ]
        video_parents = [images_task_id]
        if parent_video_tid:
            video_parents.insert(0, parent_video_tid)
        video_task_id = self._create_task(job, cmds, 'create-preview-video', 'video-encoding',
                                          parents=video_parents, priority=task_priority)
        return images_task_id, video_task_id

    def _make_progressive_render_tasks(self,
                                       job, name_fmt, parents,
                                       cycles_num_chunks: int,
                                       cycles_chunk_start: int,
                                       cycles_chunk_end: int,
                                       task_priority: int):
        """Creates the render tasks for this job.

        :param parents: either a list of parents, one for each task, or a
            single parent used for all tasks.

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

            render_output = self._render_output(cycles_chunk_start, cycles_chunk_end)

            task_cmds = [
                commands.BlenderRenderProgressive(
                    blender_cmd=job_settings['blender_cmd'],
                    filepath=job_settings['filepath'],
                    format=job_settings.get('format'),
                    # Don't render to actual render output, but to an intermediate file.
                    render_output=str(render_output),
                    frames=frame_range_bstyle,
                    cycles_num_chunks=cycles_num_chunks,
                    cycles_chunk_start=cycles_chunk_start,
                    cycles_chunk_end=cycles_chunk_end,
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
        render_fname = 'render-smpl-%04i-%04i-######' % (cycles_samples_from, cycles_samples_to)
        render_output = self.intermediate_path / render_fname
        return render_output

    def _merge_output(self, cycles_samples_to) -> PurePath:
        """Intermediate merge output path, with ###### placeholder for the frame nr"""
        merge_fname = 'merge-smpl-%04i-######' % cycles_samples_to
        merge_output = self.intermediate_path / merge_fname
        return merge_output

    def _iter_frame_chunks(self) -> typing.Iterable[typing.List[int]]:
        """Iterates over the frame chunks"""
        from flamenco.utils import iter_frame_range

        yield from iter_frame_range(self.job_settings['frames'], self.job_settings['chunk_size'])

    def _make_merge_tasks(self, job, name_fmt,
                          cycles_chunk_idx,
                          parents1, parents2,
                          cycles_chunks_to1,
                          cycles_chunks_from2,
                          cycles_chunks_to2,
                          task_priority):
        """Creates merge tasks for each chunk, consisting of merges for each frame.

        :param cycles_chunk_idx: base-1 sample chunk index

        """

        # Merging cannot happen unless we have at least two chunks
        assert cycles_chunk_idx >= 2

        from flamenco.utils import frame_range_merge

        task_ids = []

        weight1 = cycles_chunks_to1
        weight2 = cycles_chunks_to2 - cycles_chunks_from2 + 1

        # Replace Blender formatting with Python formatting in render output path
        if cycles_chunk_idx == 2:
            # The first merge takes a render output as input1, subsequent ones take merge outputs.
            # Merging only happens from Cycles chunk 2 (it needs two inputs, hence 2 chunks).
            input1 = self._render_output(1, cycles_chunks_to1)
        else:
            input1 = self._merge_output(cycles_chunks_to1)
        input2 = self._render_output(cycles_chunks_from2, cycles_chunks_to2)
        output = self._merge_output(cycles_chunks_to2)

        # Construct format strings from the paths.
        input1_fmt = str(input1).replace('######', '%06i.exr')
        input2_fmt = str(input2).replace('######', '%06i.exr')
        output_fmt = str(output).replace('######', '%06i.exr')

        blender_cmd = job['settings']['blender_cmd']
        for chunk_idx, chunk_frames in enumerate(self._iter_frame_chunks()):
            # Create a merge command for every frame in the chunk.
            task_cmds = []
            for framenr in chunk_frames:
                intermediate = output_fmt % framenr
                task_cmds.append(
                    commands.MergeProgressiveRenders(
                        blender_cmd=blender_cmd,
                        input1=input1_fmt % framenr,
                        input2=input2_fmt % framenr,
                        output=intermediate,
                        weight1=weight1,
                        weight2=weight2,
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

    def insert_rna_overrides_task(self, job: dict) -> ObjectId:
        """Inject a new RNA Overrides task into an existing job.

        Returns the new task ID.
        """
        return self._insert_rna_overrides_task(job, {'name': 'destroy-preexisting-intermediate'})
