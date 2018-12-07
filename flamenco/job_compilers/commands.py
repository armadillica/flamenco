import typing

import attr


@attr.s(auto_attribs=True)
class AbstractCommand(object):
    """Abstract Flamenco command.

    Command settings are defined in subclasses using attr.ib().
    """

    @classmethod
    def cmdname(cls):
        """Returns the command name."""
        from flamenco.utils import camel_case_to_lower_case_underscore

        return camel_case_to_lower_case_underscore(str(cls.__name__))

    def to_dict(self):
        """Returns a dictionary representation of this command, for JSON serialisation."""

        return {
            'name': self.cmdname(),
            'settings': attr.asdict(self),
        }


@attr.s(auto_attribs=True)
class Sleep(AbstractCommand):
    time_in_seconds: int


@attr.s(auto_attribs=True)
class Echo(AbstractCommand):
    message: str


@attr.s(auto_attribs=True)
class Exec(AbstractCommand):
    cmd: str


@attr.s(auto_attribs=True)
class BlenderRender(AbstractCommand):
    # Blender executable to run.
    blender_cmd: str
    # blend file path.
    filepath: str
    # output format.
    format: typing.Optional[str]
    # output file path, defaults to the path in the blend file itself.
    render_output: typing.Optional[str]

    # list of frames to render, as frame range string.
    frames: str


@attr.s(auto_attribs=True)
class BlenderRenderProgressive(BlenderRender):
    # Total number of Cycles sample chunks.
    cycles_num_chunks: int
    # Cycle sample chunk to render in this command.
    cycles_chunk: int

    # Cycles first sample number, base-1
    cycles_samples_from: int
    # Cycles last sample number, base-1
    cycles_samples_to: int


@attr.s(auto_attribs=True)
class BlenderRenderAudio(AbstractCommand):
    # Blender executable to run.
    blender_cmd: str
    # blend file path.
    filepath: str
    # output file path.
    render_output: str
    # frame range to render.
    frame_start: int
    frame_end: int


@attr.s(auto_attribs=True)
class MoveOutOfWay(AbstractCommand):
    """Moves a file or directory out of the way.

    The destination is the same as the source, with the source's modification
    timestamp appended to it.

    :ivar src: source path
    """

    src: str


@attr.s(auto_attribs=True)
class RemoveTree(AbstractCommand):
    """Deletes an entire directory tree, without creating any backup.

    :ivar path: path to delete
    """

    path: str


@attr.s(auto_attribs=True)
class MoveToFinal(AbstractCommand):
    """Moves a directory from one place to another, safely moving the destination out of the way.

    If the destination already exists, it will be renamed to have its modification
    timestamp appended to it.

    :ivar src: source path
    :ivar dest: destination path
    """

    src: str
    dest: str


@attr.s(auto_attribs=True)
class CopyFile(AbstractCommand):
    """Copies a file from one place to another.

    :ivar src: source path
    :ivar dest: destination path
    """

    src: str
    dest: str


@attr.s(auto_attribs=True)
class MergeProgressiveRenders(AbstractCommand):
    """Merges two Cycles outputs into one by taking the weighted average.
    """

    input1: str
    input2: str
    output: str

    weight1: int
    weight2: int

    # Blender command to run in order to merge the two EXR files.
    # This is usually determined by the Flamenco Manager configuration.
    blender_cmd: str = '{blender}'


@attr.s(auto_attribs=True)
class CreateVideo(AbstractCommand):
    """Creates a video from an image sequence."""

    input_files: str  # Can be a glob, hence the plural.
    output_file: str
    fps: int

    # Path to the ffmpeg binary. This is usually determined by the Flamenco Manager configuration.
    ffmpeg_cmd: str = '{ffmpeg}'


@attr.s(auto_attribs=True)
class ConcatenateVideos(AbstractCommand):
    """Creates a video from a video sequence.

    Requires the video sequence to have the same codec and parameters.
    """

    input_files: str  # Can be a glob, hence the plural.
    output_file: str

    # Path to the ffmpeg binary. This is usually determined by the Flamenco Manager configuration.
    ffmpeg_cmd: str = '{ffmpeg}'

    # Place '_001' (or higher number) in the output name, after any other
    # number-and-underscore characters.
    counter_in_output_name: bool = False


@attr.s(auto_attribs=True)
class MuxAudio(AbstractCommand):
    """Combine audio and video into an output file."""

    audio_file: str
    video_file: str
    output_file: str

    # Path to the ffmpeg binary. This is usually determined by the Flamenco Manager configuration.
    ffmpeg_cmd: str = '{ffmpeg}'


@attr.s(auto_attribs=True)
class EncodeAudio(AbstractCommand):
    """Reencode audio using FFmpeg."""

    input_file: str
    codec: str
    bitrate: str  # like '192k'
    output_file: str

    # Path to the ffmpeg binary. This is usually determined by the Flamenco Manager configuration.
    ffmpeg_cmd: str = '{ffmpeg}'


@attr.s(auto_attribs=True)
class RemoveFile(AbstractCommand):
    """Remove a file if it exists."""

    path: str


@attr.s(auto_attribs=True)
class MoveWithCounter(AbstractCommand):
    """Move a file to a new place, adding a counter to the filename to ensure uniqueness.

    If the file starts with a number-and-underscores prefix, the counter is
    added after that prefix. Otherwise the counter is added at the end of the
    filename stem (so just before the extension).
    """

    src: str
    dest: str
