import attr


@attr.s
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


@attr.s
class Sleep(AbstractCommand):
    time_in_seconds = attr.ib(validator=attr.validators.instance_of(int))


@attr.s
class Echo(AbstractCommand):
    message = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class BlenderRender(AbstractCommand):
    # Blender executable to run.
    blender_cmd = attr.ib(validator=attr.validators.instance_of(str))
    # blend file path.
    filepath = attr.ib(validator=attr.validators.instance_of(str))
    # output format.
    format = attr.ib(validator=attr.validators.optional(attr.validators.instance_of(str)))
    # output file path, defaults to the path in the blend file itself.
    render_output = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(str)))

    # list of frames to render, as frame range string.
    frames = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class BlenderRenderProgressive(BlenderRender):
    # Total number of Cycles sample chunks.
    cycles_num_chunks = attr.ib(validator=attr.validators.instance_of(int))
    # Cycle sample chunk to render in this command.
    cycles_chunk = attr.ib(validator=attr.validators.instance_of(int))

    # Cycles first sample number, base-1
    cycles_samples_from = attr.ib(validator=attr.validators.instance_of(int))
    # Cycles last sample number, base-1
    cycles_samples_to = attr.ib(validator=attr.validators.instance_of(int))


@attr.s
class MoveOutOfWay(AbstractCommand):
    """Moves a file or directory out of the way.

    The destination is the same as the source, with the source's modification
    timestamp appended to it.

    :ivar src: source path
    """

    src = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class RemoveTree(AbstractCommand):
    """Deletes an entire directory tree, without creating any backup.

    :ivar path: path to delete
    """

    path = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class MoveToFinal(AbstractCommand):
    """Moves a directory from one place to another, safely moving the destination out of the way.

    If the destination already exists, it will be renamed to have its modification
    timestamp appended to it.

    :ivar src: source path
    :ivar dest: destination path
    """

    src = attr.ib(validator=attr.validators.instance_of(str))
    dest = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class CopyFile(AbstractCommand):
    """Copies a file from one place to another.

    :ivar src: source path
    :ivar dest: destination path
    """

    src = attr.ib(validator=attr.validators.instance_of(str))
    dest = attr.ib(validator=attr.validators.instance_of(str))


@attr.s
class MergeProgressiveRenders(AbstractCommand):
    """Merges two Cycles outputs into one by taking the weighted average.
    """

    input1 = attr.ib(validator=attr.validators.instance_of(str))
    input2 = attr.ib(validator=attr.validators.instance_of(str))
    output = attr.ib(validator=attr.validators.instance_of(str))

    weight1 = attr.ib(validator=attr.validators.instance_of(int))
    weight2 = attr.ib(validator=attr.validators.instance_of(int))

    # Blender command to run in order to merge the two EXR files.
    # This is usually determined by the Flamenco Manager configuration.
    blender_cmd = attr.ib(validator=attr.validators.instance_of(str),
                          default='{blender}')
