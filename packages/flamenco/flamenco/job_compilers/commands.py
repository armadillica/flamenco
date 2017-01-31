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

        return camel_case_to_lower_case_underscore(unicode(cls.__name__))

    def to_dict(self):
        """Returns a dictionary representation of this command, for JSON serialisation."""

        return {
            u'name': self.cmdname(),
            u'settings': attr.asdict(self),
        }


@attr.s
class Sleep(AbstractCommand):
    time_in_seconds = attr.ib(validator=attr.validators.instance_of(int))


@attr.s
class Echo(AbstractCommand):
    message = attr.ib(validator=attr.validators.instance_of(unicode))


@attr.s
class BlenderRender(AbstractCommand):
    # Blender executable to run.
    blender_cmd = attr.ib(validator=attr.validators.instance_of(unicode))
    # blend file path.
    filepath = attr.ib(validator=attr.validators.instance_of(unicode))
    # output format.
    format = attr.ib(validator=attr.validators.optional(attr.validators.instance_of(unicode)))
    # output file path, defaults to the path in the blend file itself.
    render_output = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(unicode)))

    # list of frames to render, as frame range string.
    frames = attr.ib(validator=attr.validators.instance_of(unicode))


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

    src = attr.ib(validator=attr.validators.instance_of(unicode))


@attr.s
class MergeProgressiveRenders(AbstractCommand):
    """Merges two Cycles outputs into one by taking the weighted average.
    """

    input1 = attr.ib(validator=attr.validators.instance_of(unicode))
    input2 = attr.ib(validator=attr.validators.instance_of(unicode))
    output = attr.ib(validator=attr.validators.instance_of(unicode))

    weight1 = attr.ib(validator=attr.validators.instance_of(int))
    weight2 = attr.ib(validator=attr.validators.instance_of(int))

    # Blender command to run in order to merge the two EXR files.
    # This is usually determined by the Flamenco Manager configuration.
    blender_cmd = attr.ib(validator=attr.validators.instance_of(unicode),
                          default=u'{blender}')
